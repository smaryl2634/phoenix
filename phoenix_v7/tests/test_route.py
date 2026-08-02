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


def test_route_forces_stream_false_when_target_is_turbofieldfare(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "load_tier_overrides", lambda: (False, {}))
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "gemma-4-26b-a4b-it",
        "messages": [{"role": "user", "content": "在吗"}],
        "stream": True,
    }
    result = phoenix_v7._route(request, session_id="test-stream-1", provider="turbofieldfare")
    assert result is not None
    assert result["request"]["stream"] is False


def test_route_does_not_touch_stream_for_non_turbofieldfare_provider(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "load_tier_overrides", lambda: (False, {}))
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "z-ai/glm-5.2",
        "messages": [{"role": "user", "content": "在吗"}],
        "stream": True,
    }
    result = phoenix_v7._route(request, session_id="test-stream-2", provider="nous")
    assert result is None  # 没有任何改动，不应该返回替换


def test_route_leaves_stream_false_alone_for_turbofieldfare(monkeypatch):
    # stream 本来就是 False，不该因为这条逻辑触发一次"假变化"返回
    monkeypatch.setattr(phoenix_v7, "load_tier_overrides", lambda: (False, {}))
    phoenix_v7._last_tier_by_session.clear()
    request = {
        "model": "gemma-4-26b-a4b-it",
        "messages": [{"role": "user", "content": "在吗"}],
        "stream": False,
    }
    result = phoenix_v7._route(request, session_id="test-stream-3", provider="turbofieldfare")
    assert result is None


def test_route_caches_provider_and_privacy_flag_per_session(monkeypatch):
    monkeypatch.setattr(phoenix_v7, "load_tier_overrides", lambda: (False, {}))
    phoenix_v7._last_tier_by_session.clear()
    phoenix_v7._current_provider_by_session.clear()
    phoenix_v7._privacy_flagged_by_session.clear()
    request = {
        "model": "default-model",
        "messages": [{"role": "user", "content": "我的手机号是13812345678"}],
    }
    phoenix_v7._route(request, session_id="test-cache-1", provider="nous")
    assert phoenix_v7._current_provider_by_session["test-cache-1"] == "nous"
    assert phoenix_v7._privacy_flagged_by_session["test-cache-1"] is True


def test_route_caches_provider_even_when_not_primary(monkeypatch):
    # 早退路径（已经在非主线路上）也要刷新缓存——不然 transform_llm_output 侧
    # 读到的是上一轮的陈旧值。
    monkeypatch.setattr(phoenix_v7, "_primary_provider", "nous")
    phoenix_v7._current_provider_by_session.clear()
    phoenix_v7._privacy_flagged_by_session.clear()
    request = {"model": "default-model", "messages": [{"role": "user", "content": "在吗"}]}
    result = phoenix_v7._route(request, session_id="test-cache-2", provider="turbofieldfare")
    assert result is None  # 早退逻辑本身不变
    assert phoenix_v7._current_provider_by_session["test-cache-2"] == "turbofieldfare"
    assert phoenix_v7._privacy_flagged_by_session["test-cache-2"] is False
