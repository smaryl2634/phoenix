import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selfheal.antibody import AntibodyLibrary
from selfheal.error_processor import ErrorProcessor


def test_known_error_returns_fix_without_escalating():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("timeout", "增加超时时间重试")
        proc = ErrorProcessor(antibody=lib)
        outcome = proc.handle(tool_name="fetch", error_message="request timeout after 30s")
        assert outcome.escalate is False
        assert outcome.fix_hint == "增加超时时间重试"


def test_unknown_error_escalates_after_three_attempts():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        proc = ErrorProcessor(antibody=lib)
        for _ in range(2):
            outcome = proc.handle(tool_name="fetch", error_message="weird unknown error")
            assert outcome.escalate is False
        outcome = proc.handle(tool_name="fetch", error_message="weird unknown error")
        assert outcome.escalate is True


def test_pending_fix_isolated_by_session(tmp_path):
    antibody = AntibodyLibrary(storage_path=tmp_path / "antibody.json")
    processor = ErrorProcessor(antibody=antibody)

    processor.record_pending_fix("session-A", "terminal", "pattern-A")
    processor.record_pending_fix("session-B", "terminal", "pattern-B")

    # 两个session对同一个工具名各自记录的待验证修复，互不干扰
    assert processor.pop_pending_fix("session-A", "terminal") == "pattern-A"
    assert processor.pop_pending_fix("session-B", "terminal") == "pattern-B"


def test_pop_pending_fix_consumes_once(tmp_path):
    antibody = AntibodyLibrary(storage_path=tmp_path / "antibody.json")
    processor = ErrorProcessor(antibody=antibody)

    processor.record_pending_fix("session-A", "terminal", "pattern-A")
    first = processor.pop_pending_fix("session-A", "terminal")
    second = processor.pop_pending_fix("session-A", "terminal")

    assert first == "pattern-A"
    assert second is None


def test_pop_pending_fix_missing_returns_none(tmp_path):
    antibody = AntibodyLibrary(storage_path=tmp_path / "antibody.json")
    processor = ErrorProcessor(antibody=antibody)
    assert processor.pop_pending_fix("session-X", "todo") is None


def test_pending_fix_isolated_by_tool_within_same_session(tmp_path):
    # test_pending_fix_isolated_by_session 只覆盖了"同工具不同session"这一半的
    # key 组合——一个只按 session_id 建key（漏掉 tool_name）的错误实现也能通过
    # 那条测试。这条补上另一半：同一个session里两个不同工具各自记录的待验证
    # 修复，也必须互不干扰。
    antibody = AntibodyLibrary(storage_path=tmp_path / "antibody.json")
    processor = ErrorProcessor(antibody=antibody)

    processor.record_pending_fix("session-A", "toolX", "pattern-X")
    processor.record_pending_fix("session-A", "toolY", "pattern-Y")

    assert processor.pop_pending_fix("session-A", "toolX") == "pattern-X"
    assert processor.pop_pending_fix("session-A", "toolY") == "pattern-Y"
