"""日/月成本追踪 —— V6.1 cost_monitor.py 确认为真实可用的设计，原样移植逻辑."""
from __future__ import annotations

import json
import time
from pathlib import Path


class CostMonitor:
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
        return {"entries": []}  # each entry: {"ts": float, "usd": float}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data), encoding="utf-8")

    def record(self, usd: float) -> None:
        self._data["entries"].append({"ts": time.time(), "usd": usd})
        self._save()

    def _sum_since(self, seconds_ago: float) -> float:
        cutoff = time.time() - seconds_ago
        return sum(e["usd"] for e in self._data["entries"] if e["ts"] >= cutoff)

    def is_over_limit(self, daily_limit: float, monthly_limit: float) -> bool:
        daily = self._sum_since(24 * 3600)
        monthly = self._sum_since(30 * 24 * 3600)
        return daily > daily_limit or monthly > monthly_limit

    def daily_total(self) -> float:
        return self._sum_since(24 * 3600)

    def monthly_total(self) -> float:
        return self._sum_since(30 * 24 * 3600)
