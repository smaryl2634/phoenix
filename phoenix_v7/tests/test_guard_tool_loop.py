import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".hermes" / "hermes-agent"))
sys.path.insert(0, str(Path.home() / ".hermes" / "plugins"))

import phoenix_v7


def _patch_goal(monkeypatch, *, active: bool, created_at: float = 100.0, seeded: bool = False):
    monkeypatch.setattr(phoenix_v7, "_is_goal_active", lambda session_id: active)
    monkeypatch.setattr(phoenix_v7, "_goal_created_at", lambda session_id: created_at if active else None)
    monkeypatch.setattr(phoenix_v7, "_is_checklist_seeded", lambda session_id, goal_created_at: seeded)


def test_guard_tool_blocks_non_whitelisted_tool_when_loop_active_unseeded(monkeypatch):
    _patch_goal(monkeypatch, active=True, seeded=False)
    result = phoenix_v7._guard_tool("terminal", {}, session_id="sess-loop-1")
    assert result["rule_key"] == "phoenix_v7_loop_checklist_required"


def test_guard_tool_allows_todo_and_marks_seeded(monkeypatch):
    _patch_goal(monkeypatch, active=True, created_at=100.0, seeded=False)
    seeded_calls = []
    monkeypatch.setattr(
        phoenix_v7, "_mark_checklist_seeded",
        lambda session_id, goal_created_at: seeded_calls.append((session_id, goal_created_at)),
    )
    result = phoenix_v7._guard_tool("todo", {"todos": []}, session_id="sess-loop-2")
    assert result is None
    assert seeded_calls == [("sess-loop-2", 100.0)]


def test_guard_tool_no_active_loop_unaffected(monkeypatch):
    _patch_goal(monkeypatch, active=False)
    phoenix_v7._last_tier_by_session["sess-no-loop"] = "l1_daily"
    result = phoenix_v7._guard_tool("terminal", {}, session_id="sess-no-loop")
    assert result is None


def test_guard_tool_loop_active_seeded_high_tier_blocks_for_evaluator(monkeypatch):
    _patch_goal(monkeypatch, active=True, seeded=True)
    phoenix_v7._last_tier_by_session["sess-loop-3"] = "l3_critical"
    result = phoenix_v7._guard_tool("terminal", {}, session_id="sess-loop-3")
    assert result["rule_key"] == "phoenix_v7_loop_high_tier_needs_evaluator"


def test_subagent_stop_records_approval_on_approved_summary():
    phoenix_v7._pending_loop_approvals.clear()
    phoenix_v7._on_subagent_stop(
        parent_session_id="sess-eval-1",
        child_summary="APPROVED: 这个操作看起来是安全的，可以执行",
        child_status="completed",
    )
    assert phoenix_v7._pending_loop_approvals.get("sess-eval-1") is True


def test_subagent_stop_case_insensitive_approved_prefix():
    phoenix_v7._pending_loop_approvals.clear()
    phoenix_v7._on_subagent_stop(
        parent_session_id="sess-eval-2",
        child_summary="approved, looks fine",
        child_status="completed",
    )
    assert phoenix_v7._pending_loop_approvals.get("sess-eval-2") is True


def test_subagent_stop_rejected_summary_does_not_record_approval():
    phoenix_v7._pending_loop_approvals.clear()
    phoenix_v7._on_subagent_stop(
        parent_session_id="sess-eval-3",
        child_summary="REJECTED: 这个操作风险太高，不应该执行",
        child_status="completed",
    )
    assert "sess-eval-3" not in phoenix_v7._pending_loop_approvals


def test_subagent_stop_missing_parent_session_id_is_noop():
    phoenix_v7._pending_loop_approvals.clear()
    phoenix_v7._on_subagent_stop(parent_session_id="", child_summary="APPROVED", child_status="completed")
    assert phoenix_v7._pending_loop_approvals == {}


def test_guard_tool_consumes_pending_approval_and_allows_once(monkeypatch):
    _patch_goal(monkeypatch, active=True, seeded=True)
    phoenix_v7._last_tier_by_session["sess-eval-4"] = "l3_critical"
    phoenix_v7._pending_loop_approvals["sess-eval-4"] = True

    first = phoenix_v7._guard_tool("terminal", {}, session_id="sess-eval-4")
    assert first is None  # 批准被消费，第一次放行

    second = phoenix_v7._guard_tool("terminal", {}, session_id="sess-eval-4")
    assert second["rule_key"] == "phoenix_v7_loop_high_tier_needs_evaluator"  # 批准已用掉，第二次照样拦


def test_guard_tool_high_tier_todo_call_does_not_mark_seeded_until_allowed(monkeypatch):
    _patch_goal(monkeypatch, active=True, created_at=100.0, seeded=False)
    seeded_calls = []
    monkeypatch.setattr(
        phoenix_v7, "_mark_checklist_seeded",
        lambda session_id, goal_created_at: seeded_calls.append((session_id, goal_created_at)),
    )
    phoenix_v7._last_tier_by_session["sess-high-todo"] = "l3_critical"
    phoenix_v7._pending_loop_approvals.pop("sess-high-todo", None)

    blocked = phoenix_v7._guard_tool("todo", {"todos": []}, session_id="sess-high-todo")
    assert blocked["rule_key"] == "phoenix_v7_loop_high_tier_needs_evaluator"
    assert seeded_calls == []

    phoenix_v7._pending_loop_approvals["sess-high-todo"] = True
    allowed = phoenix_v7._guard_tool("todo", {"todos": []}, session_id="sess-high-todo")
    assert allowed is None
    assert seeded_calls == [("sess-high-todo", 100.0)]
