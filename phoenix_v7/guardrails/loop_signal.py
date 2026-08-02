"""读取 Hermes 原生 `/goal`（Ralph loop）状态——不死鸟的 Loop 长任务相关逻辑（清单
强制、无人值守高危操作复核）不再自己判断"要不要激活长任务模式"，而是直接读 Hermes
自己的判断。跟 __init__.py::_load_primary_provider() 读 config.yaml 判断主 provider
是同一手法：直接 import Hermes 内部模块，不通过官方钩子 context（因为钩子 context
里没有 goal 相关字段）。

`GoalManager` 只读不写——这里从不调用 set()/clear()/pause()/resume()，不会干扰用户
自己对 /goal 的操作。
"""
from __future__ import annotations


def _get_goal_manager(session_id: str):
    """独立出来的一层，方便测试用 monkeypatch 替换掉真实的 GoalManager 构造。"""
    from hermes_cli.goals import GoalManager

    return GoalManager(session_id)


def _is_goal_active(session_id: str) -> bool:
    """这个 session 当前有没有激活的 /goal。读取失败（模块导入失败、SessionDB 读取
    异常等）一律返回 False——降级方向是"当作没有 goal"，不会误拦任何工具调用。"""
    if not session_id:
        return False
    try:
        return bool(_get_goal_manager(session_id).is_active())
    except Exception:
        return False


def _goal_created_at(session_id: str) -> float | None:
    """当前激活 goal 的 created_at 时间戳，用于区分"同一个 goal 周期"还是"新一轮
    goal"。没有激活的 goal 或读取失败都返回 None。"""
    if not session_id:
        return None
    try:
        manager = _get_goal_manager(session_id)
        if not manager.is_active():
            return None
        return manager.state.created_at
    except Exception:
        return None


# session_id -> (goal 的 created_at 时间戳, 这个 goal 周期是否已经建过清单)。
# 进程内内存状态，重启（= 重启 hermes 进程）后清空是可接受的行为——跟 __init__.py 里
# _pending_loop_approvals/_last_tier_by_session 是同一种设计取舍，不需要持久化。
_checklist_seeded_by_session: dict[str, tuple[float, bool]] = {}


def _is_checklist_seeded(session_id: str, goal_created_at: float) -> bool:
    entry = _checklist_seeded_by_session.get(session_id)
    if entry is None or entry[0] != goal_created_at:
        return False
    return entry[1]


def _mark_checklist_seeded(session_id: str, goal_created_at: float) -> None:
    _checklist_seeded_by_session[session_id] = (goal_created_at, True)
