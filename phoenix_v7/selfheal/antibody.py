"""错误模式→处理建议查表 —— 对应V6.1 antibody.py 确认为真实可用的字符串包含匹配设计,
含成功率统计+连续失败自动停用."""
from __future__ import annotations

import json
from pathlib import Path

_DISABLE_AFTER_CONSECUTIVE_FAILURES = 3


class AntibodyLibrary:
    def __init__(self, storage_path: Path) -> None:
        self._path = storage_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"entries": {}}  # pattern -> {"fix": str, "consecutive_failures": int, "disabled": bool}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")

    def record(self, error_pattern: str, fix_action: str) -> None:
        self._data["entries"][error_pattern] = {
            "fix": fix_action,
            "consecutive_failures": 0,
            "disabled": False,
        }
        self._save()

    def record_outcome(self, error_pattern: str, success: bool) -> None:
        entry = self._data["entries"].get(error_pattern)
        if entry is None:
            return
        if success:
            entry["consecutive_failures"] = 0
            entry["disabled"] = False
        else:
            entry["consecutive_failures"] += 1
            if entry["consecutive_failures"] >= _DISABLE_AFTER_CONSECUTIVE_FAILURES:
                entry["disabled"] = True
        self._save()

    def lookup(self, error_message: str) -> str | None:
        for pattern, entry in self._data["entries"].items():
            if entry.get("disabled"):
                continue
            if pattern in error_message:
                return entry["fix"]
        return None

    def match_pattern(self, error_message: str) -> str | None:
        """返回命中(且未disabled)的模式串本身（record_outcome的key），而非其fix建议。
        Task 11 接入时发现：record_outcome 按 dict 精确匹配 pattern key，调用方手上
        通常只有完整的原始 error_message（是 pattern 的超集，不是同一个字符串），
        直接传 error_message 进 record_outcome 会静默 no-op（entry 找不到）。"""
        for pattern, entry in self._data["entries"].items():
            if entry.get("disabled"):
                continue
            if pattern in error_message:
                return pattern
        return None

    def stats(self) -> dict:
        entries = self._data["entries"]
        return {
            "total_patterns": len(entries),
            "disabled_patterns": sum(1 for e in entries.values() if e.get("disabled")),
        }
