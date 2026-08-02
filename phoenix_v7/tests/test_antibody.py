import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selfheal.antibody import AntibodyLibrary


def test_lookup_returns_none_when_no_match():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        assert lib.lookup("some random error") is None


def test_lookup_finds_substring_match():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("connection refused", "检查目标服务是否启动，端口是否被占用")
        result = lib.lookup("Error: connection refused on port 8080")
        assert result == "检查目标服务是否启动，端口是否被占用"


def test_entry_auto_disabled_after_three_consecutive_failures():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("flaky error", "重试一次")
        lib.record_outcome("flaky error", success=False)
        lib.record_outcome("flaky error", success=False)
        lib.record_outcome("flaky error", success=False)
        assert lib.lookup("this is a flaky error case") is None


def test_success_resets_failure_streak():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("flaky error", "重试一次")
        lib.record_outcome("flaky error", success=False)
        lib.record_outcome("flaky error", success=False)
        lib.record_outcome("flaky error", success=True)
        lib.record_outcome("flaky error", success=False)
        assert lib.lookup("this is a flaky error case") == "重试一次"


def test_match_pattern_returns_the_pattern_key_not_the_fix():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("No such file or directory", "文件路径写错了，检查路径拼写")
        matched = lib.match_pattern("[Errno 2] No such file or directory: '/tmp/x.txt'")
        assert matched == "No such file or directory"


def test_record_outcome_with_raw_superset_message_is_a_silent_noop():
    """记录这条已知的调用方陷阱：record_outcome 要求精确匹配 pattern key，
    传原始 error_message（pattern 的超集）不会报错，但也不会更新任何状态——
    Task 11 接入 __init__.py 时必须先用 match_pattern 换出真正的 key。"""
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("No such file or directory", "文件路径写错了，检查路径拼写")
        lib.record_outcome("[Errno 2] No such file or directory: '/tmp/x.txt'", success=False)
        entries = lib._data["entries"]
        assert entries["No such file or directory"]["consecutive_failures"] == 0


def test_stats_counts_patterns_and_disabled():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        lib.record("error pattern A", "fix A")
        lib.record("error pattern B", "fix B")
        # 让 pattern B 连续失败3次自动停用
        lib.record_outcome("error pattern B", success=False)
        lib.record_outcome("error pattern B", success=False)
        lib.record_outcome("error pattern B", success=False)

        stats = lib.stats()
        assert stats["total_patterns"] == 2
        assert stats["disabled_patterns"] == 1


def test_stats_empty_library():
    with tempfile.TemporaryDirectory() as d:
        lib = AntibodyLibrary(storage_path=Path(d) / "antibody.json")
        stats = lib.stats()
        assert stats == {"total_patterns": 0, "disabled_patterns": 0}
