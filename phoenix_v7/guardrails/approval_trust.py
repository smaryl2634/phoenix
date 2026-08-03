"""审批信任记录——不死鸟自己那道"高危操作需要确认"的门槛
(guardrails/tool_guard.py::evaluate())目前所有操作共用同一套标准，每次都问。
这个模块让它按工具类型(tool_name)记住"历史上连续批准过几次"，攒够信任就不再
触发；用户拒绝一次立刻清零重新累积。

跟 Hermes 自己的 `hermes approvals suggest`（挖历史批准记录建议永久allowlist）
是两套完全独立的机制——那套只覆盖 Hermes 自己判断的危险命令，管不到这道基于
消息内容判定的"真神档"门槛，这里补的是它管不到的真空区，不是重复实现。"""
from __future__ import annotations

import json
from pathlib import Path

TRUST_THRESHOLD = 3

# 这几种选择代表用户真的看过、同意了这次操作——不管是一次性同意(once)、这个
# session内同意(session)、永久同意(always)，还是Hermes smart模式下辅助LLM
# 判定为可以自动放行(smart_approve)，都算一次真实的"信任积累"。
_TRUSTED_CHOICES = {"once", "session", "always", "smart_approve"}

# 用户明确说不——不管是人工拒绝还是smart模式判定拒绝，都代表这类操作现在还
# 不该被信任，立刻清零重新开始累积，不能让之前攒的信任继续生效。
_RESET_CHOICES = {"deny", "smart_deny"}

# timeout 不在上面两个集合里，是刻意的：用户没来得及回应不等于用户说"不"，
# 不能把"不在场"当成"拒绝"处理，也不能当成"同意"——保持计数不变，什么都不做。


def _default_store_path() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "phoenix_v7_state" / "approval_trust.json"


def _load(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}


def _save(path: Path, data: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_approval_outcome(
    bucket_key: str, choice: str, path: Path | None = None
) -> None:
    """记录一次审批结果。choice 是 Hermes post_approval_response 钩子传来的
    真实用户选择。信任类选择计数+1，拒绝类选择清零，中性结果（比如timeout）
    不改变计数、不重写文件。"""
    target = path or _default_store_path()
    data = _load(target)
    current = data.get(bucket_key, 0)
    if choice in _TRUSTED_CHOICES:
        data[bucket_key] = current + 1
    elif choice in _RESET_CHOICES:
        data[bucket_key] = 0
    else:
        return
    _save(target, data)


def is_approval_trusted(bucket_key: str, path: Path | None = None) -> bool:
    """这个桶累计的连续信任次数是否达到阈值。"""
    target = path or _default_store_path()
    data = _load(target)
    return data.get(bucket_key, 0) >= TRUST_THRESHOLD
