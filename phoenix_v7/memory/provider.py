"""官方 MemoryProvider ABC 实现，包裹 memory/store.py 的纯逻辑."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider  # Hermes宿主自己的模块，保持绝对import

from .store import MemoryStore  # 同package内的兄弟模块，相对import


class PhoenixMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._store: MemoryStore | None = None

    @property
    def name(self) -> str:
        return "phoenix_v7"

    def is_available(self) -> bool:
        return True  # 纯本地JSON存储，不依赖网络/外部凭证

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        hermes_home = kwargs.get("hermes_home") or str(Path.home() / ".hermes")
        storage_path = Path(hermes_home) / "phoenix_v7_memory.json"
        self._store = MemoryStore(storage_path=storage_path)

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._store is None:
            return ""
        results = self._store.recall(query, session_id=session_id)
        if not results:
            return ""
        return "已知信息：\n" + "\n".join(f"- {r}" for r in results)

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: List[Dict[str, Any]] | None = None,
    ) -> None:
        if self._store is None:
            return
        self._store.add_short_term(session_id, "user", user_content)
        self._store.add_short_term(session_id, "assistant", assistant_content)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return []  # V1 无需任何配置，纯本地JSON存储零配置可用

    def backup_paths(self) -> List[str]:
        return []  # 存储就在 HERMES_HOME 下，hermes backup 默认已经覆盖，无需额外声明

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        # Hermes 要压缩上下文丢弃旧消息前，把这些消息里能提炼的事实先存一份。
        # V1 做法很简单：把每条 user 消息整句存成 fact，不做语义提炼（YAGNI，
        # 语义抽取质量问题留给用了之后再决定要不要加强）。
        if self._store is None:
            return ""
        for msg in messages:
            if msg.get("role") == "user":
                content = str(msg.get("content", "")).strip()
                if content:
                    self._store.add_fact(content)
        return ""
