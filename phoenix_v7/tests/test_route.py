import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".hermes" / "hermes-agent"))
sys.path.insert(0, str(Path.home() / ".hermes" / "plugins"))

import phoenix_v7


def test_route_disabled_updates_tier_state_but_returns_none(monkeypatch):
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (False, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-1")
    assert result is None
    assert phoenix_v7._last_tier_by_session["test-session-1"] == "l2_deep"


def test_route_enabled_switches_model_when_tier_has_override(monkeypatch):
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (True, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-2")
    assert result is not None
    assert result["request"]["model"] == "smart-model"
    assert phoenix_v7._last_tier_by_session["test-session-2"] == "l2_deep"


def test_route_enabled_but_tier_has_no_override_returns_none(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "load_tier_overrides", lambda: (True, {}))
    phoenix_v7._last_tier_by_session.clear()
    request = {"model": "default-model", "messages": [{"role": "user", "content": "在吗"}]}
    result = phoenix_v7._route(request, session_id="test-session-3")
    assert result is None
    assert phoenix_v7._last_tier_by_session["test-session-3"] == "l0_fast"


def test_load_primary_provider_reads_model_provider(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "model:\n  provider: nous\n  default: z-ai/glm-5.2\n", encoding="utf-8"
    )
    assert phoenix_v7._load_primary_provider(path=config_path) == "nous"


def test_load_primary_provider_missing_file_returns_empty(tmp_path):
    assert phoenix_v7._load_primary_provider(path=tmp_path / "does_not_exist.yaml") == ""


def test_load_primary_provider_malformed_yaml_returns_empty(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("not: valid: yaml: [", encoding="utf-8")
    assert phoenix_v7._load_primary_provider(path=config_path) == ""


def test_load_primary_provider_missing_model_key_returns_empty(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("web:\n  backend: firecrawl\n", encoding="utf-8")
    assert phoenix_v7._load_primary_provider(path=config_path) == ""


def test_route_skips_when_provider_is_not_primary(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "_primary_provider", "nous")
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (True, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-6", provider="custom")
    assert result is None


def test_route_proceeds_when_provider_matches_primary(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "_primary_provider", "nous")
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (True, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-7", provider="nous")
    assert result is not None
    assert result["request"]["model"] == "smart-model"


def test_route_proceeds_when_provider_context_missing(monkeypatch):
    # 兼容旧调用方式——context 里没带 provider 字段时不应该被新逻辑挡住
    monkeypatch.setattr(phoenix_v7, "_primary_provider", "nous")
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (True, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-8")
    assert result is not None
    assert result["request"]["model"] == "smart-model"


def test_route_proceeds_when_primary_provider_unresolved(monkeypatch):
    # _primary_provider 读取配置失败时是空字符串，不该让每次请求都被误判成"不在主线路上"
    monkeypatch.setattr(phoenix_v7, "_primary_provider", "")
    monkeypatch.setattr(
        phoenix_v7, "load_tier_overrides", lambda: (True, {"l2_deep": "smart-model"})
    )
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "帮我设计一个分布式系统的一致性方案"}],
    }
    result = phoenix_v7._route(request, session_id="test-session-9", provider="anything")
    assert result is not None
    assert result["request"]["model"] == "smart-model"
