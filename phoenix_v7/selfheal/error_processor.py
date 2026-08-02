"""包裹 antibody 库，做"查表处理 / 3次失败后升级求助用户"的判断,
对应 V6.1 error_processor.py + V2文档 #19 "3次失败求助" 的合并设计."""
from __future__ import annotations

from dataclasses import dataclass

from .antibody import AntibodyLibrary  # 同package内兄弟模块，相对import

_ESCALATE_AFTER_ATTEMPTS = 3


@dataclass
class Outcome:
    escalate: bool
    fix_hint: str | None


class ErrorProcessor:
    def __init__(self, antibody: AntibodyLibrary) -> None:
        self._antibody = antibody
        self._attempt_counts: dict[str, int] = {}
        # session_id:tool_name -> 最近一次对这个工具提示过的 antibody pattern，
        # 等下一次调用同一工具时看它是不是成功了。按 session 隔离，不能只按
        # tool_name（否则两个并发session用同一个工具会互相污染自愈记录）。
        self._pending_fix: dict[str, str] = {}

    def handle(self, tool_name: str, error_message: str) -> Outcome:
        fix = self._antibody.lookup(error_message)
        if fix is not None:
            return Outcome(escalate=False, fix_hint=fix)

        key = f"{tool_name}:{error_message}"
        self._attempt_counts[key] = self._attempt_counts.get(key, 0) + 1
        if self._attempt_counts[key] >= _ESCALATE_AFTER_ATTEMPTS:
            return Outcome(escalate=True, fix_hint=None)
        return Outcome(escalate=False, fix_hint=None)

    def record_pending_fix(self, session_id: str, tool_name: str, pattern: str) -> None:
        self._pending_fix[f"{session_id}:{tool_name}"] = pattern

    def pop_pending_fix(self, session_id: str, tool_name: str) -> str | None:
        return self._pending_fix.pop(f"{session_id}:{tool_name}", None)
