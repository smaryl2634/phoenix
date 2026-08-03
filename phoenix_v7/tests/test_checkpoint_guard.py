import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.checkpoint_guard import (
    CHECKPOINT_REMINDER_TEXT,
    is_checkpoint_triggering_call,
    is_checkpoints_enabled,
)


def test_checkpoint_reminder_text_is_exact():
    assert CHECKPOINT_REMINDER_TEXT == (
        "🎮 检测到一次\"高危操作\"——就像游戏里踩雷之前的存档点，可惜这次你没存，\n"
        "翻车了没法直接读档重来。\n\n"
        "Hermes 自带\"存档\"功能（读档就是 /rollback），默认是关的。开一下：\n"
        "  hermes chat --checkpoints\n\n"
        "开完之后，每次干\"删/改\"这种活之前会自动帮你偷偷存一档，\n"
        "翻车了直接读档，不用自己肉身手动回滚。"
    )


def test_write_file_is_checkpoint_triggering():
    assert is_checkpoint_triggering_call("write_file", {"path": "/tmp/x.py"}) is True


def test_patch_is_checkpoint_triggering():
    assert is_checkpoint_triggering_call("patch", {"path": "/tmp/x.py"}) is True


def test_destructive_terminal_command_is_checkpoint_triggering():
    assert is_checkpoint_triggering_call("terminal", {"command": "rm -rf /tmp/foo"}) is True


def test_benign_terminal_command_is_not_checkpoint_triggering():
    assert is_checkpoint_triggering_call("terminal", {"command": "ls -la"}) is False


def test_terminal_with_missing_command_arg_is_not_checkpoint_triggering():
    assert is_checkpoint_triggering_call("terminal", {}) is False


def test_unrelated_tool_is_not_checkpoint_triggering():
    assert is_checkpoint_triggering_call("read_file", {"path": "/tmp/x.py"}) is False


def test_checkpoints_enabled_true(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("checkpoints:\n  enabled: true\n", encoding="utf-8")
    assert is_checkpoints_enabled(path=config_path) is True


def test_checkpoints_enabled_false(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("checkpoints:\n  enabled: false\n", encoding="utf-8")
    assert is_checkpoints_enabled(path=config_path) is False


def test_checkpoints_missing_file_returns_false():
    # 保守到"提醒"这一侧：读不到配置就当作"没开"，宁可多提醒一次，也不能因为
    # 读取失败误判成"已经开启"从而漏提醒——提醒是低成本的，漏提醒才是真正的问题
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert is_checkpoints_enabled(path=Path(d) / "does_not_exist.yaml") is False


def test_checkpoints_missing_section_returns_false(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("model:\n  provider: nous\n", encoding="utf-8")
    assert is_checkpoints_enabled(path=config_path) is False


def test_checkpoints_malformed_yaml_returns_false(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("not: valid: yaml: [", encoding="utf-8")
    assert is_checkpoints_enabled(path=config_path) is False
