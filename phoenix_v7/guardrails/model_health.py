"""模型健康追踪 —— 移植自 V6.1 model_health.py，纯内存、无副作用。

不关心候选模型属于哪个厂商/通过什么中转站访问——只按模型标识符字符串记健康状态，
天然兼容三种部署场景（中转站/单模型/多模型分Key）：单模型用户的 tiers.json 配的是
单个字符串而不是候选链，这个追踪器根本不会被调用到；多模型/中转站用户的候选链
不管是同厂商还是跨厂商，这里只是拿字符串当 key，没有任何场景专用逻辑。

进程内内存状态，重启（= 重启 hermes 进程）后清空是可接受的行为，跟
guardrails/circuit_breaker.py 是同一个设计取舍，不需要持久化。"""
from __future__ import annotations

import time
from typing import Any, Callable

_HEALTH_FAILURE_TYPES = {
    "TimeoutError", "ReadTimeout", "ConnectTimeout", "APIConnectionError",
    "BadGatewayError", "ServiceUnavailableError", "InternalServerError",
    "ServerError", "EmptyResponseError", "RateLimitError",
    "429", "500", "502", "503", "504",
}


class ModelHealthTracker:
    def __init__(
        self,
        *,
        failure_threshold: int = 2,
        cooldown_seconds: int = 60,
        now_func: Callable[[], float] = time.time,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(1, int(cooldown_seconds))
        self._now = now_func
        self._models: dict[str, dict[str, Any]] = {}

    def record_success(self, model: str) -> None:
        state = self._state_for(model)
        state["consecutive_failures"] = 0
        state["cooldown_until"] = 0.0

    def record_failure(self, model: str, error_type: str) -> None:
        if not self._counts_as_health_failure(error_type):
            return
        state = self._state_for(model)
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= self.failure_threshold:
            state["cooldown_until"] = self._now() + self.cooldown_seconds

    def is_available(self, model: str) -> bool:
        state = self._models.get(model)
        if not state:
            return True
        cooldown_until = float(state.get("cooldown_until") or 0.0)
        return not cooldown_until or self._now() >= cooldown_until

    def ordered_candidates(self, models: list[str]) -> list[str]:
        healthy = [m for m in models if self.is_available(m)]
        unhealthy = [m for m in models if not self.is_available(m)]
        return healthy + unhealthy

    def _state_for(self, model: str) -> dict[str, Any]:
        state = self._models.get(model)
        if state is None:
            state = {"consecutive_failures": 0, "cooldown_until": 0.0}
            self._models[model] = state
        return state

    @staticmethod
    def _counts_as_health_failure(error_type: str) -> bool:
        if error_type in _HEALTH_FAILURE_TYPES:
            return True
        return error_type.endswith("ServerError") or error_type.endswith("Timeout")
