"""三层记忆的纯逻辑存储 —— 对应V6.1 memory_system.py 短期/事实/纠正三层设计，
用简单JSON+关键词重合计分做召回（不引入向量检索，YAGNI，V7.1视需要再加强）."""
from __future__ import annotations

import json
import re
from pathlib import Path

_WORD_RE = re.compile(r"[a-zA-Z0-9_]+|[一-鿿]")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text))


class MemoryStore:
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
        return {"short_term": [], "facts": [], "corrections": []}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")

    def add_short_term(self, session_id: str, role: str, content: str) -> None:
        self._data["short_term"].append(
            {"session_id": session_id, "role": role, "content": content}
        )
        self._data["short_term"] = self._data["short_term"][-50:]  # 只留最近50条
        self._save()

    def add_fact(self, text: str) -> None:
        self._data["facts"].append(text)
        self._save()

    def add_correction(self, text: str) -> None:
        self._data["corrections"].append(text)
        self._save()

    def recall(self, query: str, limit: int = 5, session_id: str = "") -> list[str]:
        """按关键词重合度召回。facts/corrections 是提炼过的持久知识，跨 session 全局可查
        （这是它们存在的意义）；short_term 是"这一轮对话的原始上下文"，按 session_id 严格
        隔离——不传 session_id 时 short_term 层不参与召回，避免不同话题的原始对话互相串。
        2026-07-28修正：原来完全不看session_id，在全部历史短期记录里联想，真机验收发现
        会把毫不相关的历史对话一起召回。"""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[int, int, str]] = []
        # priority: corrections(2) > facts(1) > short_term(0) — 纠正优先于旧事实
        for priority, layer in ((2, "corrections"), (1, "facts"), (0, "short_term")):
            for entry in self._data[layer]:
                if layer == "short_term":
                    if not session_id or entry.get("session_id") != session_id:
                        continue
                    text = entry["content"]
                else:
                    text = entry["content"] if isinstance(entry, dict) else entry
                overlap = len(query_tokens & _tokenize(text))
                if overlap > 0:
                    scored.append((priority, overlap, text))

        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [text for _, _, text in scored[:limit]]
