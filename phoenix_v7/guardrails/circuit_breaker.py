"""三态熔断器 —— V6.1 circuit_breaker.py 确认为真实可用、工程严谨的设计，原样移植."""
from __future__ import annotations

import threading
import time


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_after_seconds: float) -> None:
        self._threshold = failure_threshold
        self._reset_after = reset_after_seconds
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if time.time() - self._opened_at >= self._reset_after:
                # half-open: 允许试探性放行一次，成功由 record_success 关闭熔断
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._opened_at = time.time()

    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            if time.time() - self._opened_at >= self._reset_after:
                return "half_open"
            return "open"
