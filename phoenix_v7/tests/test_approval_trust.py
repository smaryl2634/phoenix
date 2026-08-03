import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.approval_trust import (
    TRUST_THRESHOLD,
    record_approval_outcome,
    is_approval_trusted,
)


def test_trust_threshold_is_three():
    assert TRUST_THRESHOLD == 3


def test_not_trusted_when_never_recorded(tmp_path):
    path = tmp_path / "approval_trust.json"
    assert is_approval_trusted("write_file", path=path) is False


def test_trusted_after_three_consecutive_approvals(tmp_path):
    path = tmp_path / "approval_trust.json"
    record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "session", path=path)
    assert is_approval_trusted("write_file", path=path) is False  # 还差一次
    record_approval_outcome("write_file", "always", path=path)
    assert is_approval_trusted("write_file", path=path) is True


def test_smart_approve_counts_as_trust(tmp_path):
    path = tmp_path / "approval_trust.json"
    for _ in range(3):
        record_approval_outcome("terminal", "smart_approve", path=path)
    assert is_approval_trusted("terminal", path=path) is True


def test_deny_resets_count_to_zero(tmp_path):
    path = tmp_path / "approval_trust.json"
    for _ in range(3):
        record_approval_outcome("write_file", "once", path=path)
    assert is_approval_trusted("write_file", path=path) is True
    record_approval_outcome("write_file", "deny", path=path)
    assert is_approval_trusted("write_file", path=path) is False


def test_smart_deny_resets_count_to_zero(tmp_path):
    path = tmp_path / "approval_trust.json"
    for _ in range(3):
        record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "smart_deny", path=path)
    assert is_approval_trusted("write_file", path=path) is False


def test_timeout_does_not_affect_count(tmp_path):
    path = tmp_path / "approval_trust.json"
    record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "timeout", path=path)
    assert is_approval_trusted("write_file", path=path) is False  # 还是2次，没被清零也没被推进
    record_approval_outcome("write_file", "once", path=path)
    assert is_approval_trusted("write_file", path=path) is True  # 第3次真实批准后达标


def test_buckets_are_independent(tmp_path):
    path = tmp_path / "approval_trust.json"
    for _ in range(3):
        record_approval_outcome("write_file", "once", path=path)
    assert is_approval_trusted("write_file", path=path) is True
    assert is_approval_trusted("terminal", path=path) is False


def test_missing_file_returns_not_trusted(tmp_path):
    path = tmp_path / "does_not_exist.json"
    assert is_approval_trusted("write_file", path=path) is False


def test_corrupted_json_returns_not_trusted(tmp_path):
    path = tmp_path / "approval_trust.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert is_approval_trusted("write_file", path=path) is False


def test_persists_across_separate_calls(tmp_path):
    # 每次调用都独立打开/关闭文件（不维护进程内缓存），模拟跨会话/跨进程持久化
    path = tmp_path / "approval_trust.json"
    record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "once", path=path)
    record_approval_outcome("write_file", "once", path=path)
    assert is_approval_trusted("write_file", path=path) is True
    assert path.exists()
