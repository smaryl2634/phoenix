import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path.home() / ".hermes" / "hermes-agent"))

from memory.provider import PhoenixMemoryProvider


def test_is_available_without_initialize():
    provider = PhoenixMemoryProvider()
    assert provider.is_available() is True  # 纯本地JSON存储，无外部依赖，永远可用


def test_name_is_phoenix():
    provider = PhoenixMemoryProvider()
    assert provider.name == "phoenix_v7"


def test_sync_turn_then_prefetch_recalls_it():
    with tempfile.TemporaryDirectory() as d:
        provider = PhoenixMemoryProvider()
        provider.initialize(session_id="s1", hermes_home=d, platform="cli")
        provider.sync_turn(
            user_content="我们团队用飞书管理",
            assistant_content="了解，你们用飞书协作",
            session_id="s1",
        )
        recalled = provider.prefetch("团队用什么工具", session_id="s1")
        assert "飞书" in recalled


def test_get_tool_schemas_returns_empty_list():
    provider = PhoenixMemoryProvider()
    assert provider.get_tool_schemas() == []
