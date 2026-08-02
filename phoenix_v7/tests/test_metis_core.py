import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router.metis_core import classify, tier_to_model


def test_short_greeting_is_l0_fast():
    messages = [{"role": "user", "content": "在吗"}]
    assert classify(messages) == "l0_fast"


def test_simple_question_is_l1_daily():
    messages = [{"role": "user", "content": "今天北京天气怎么样"}]
    assert classify(messages) == "l1_daily"


def test_design_keyword_is_l2_deep():
    messages = [{"role": "user", "content": "帮我设计一套用户认证系统的架构"}]
    assert classify(messages) == "l2_deep"


def test_critical_keyword_is_l3_critical():
    messages = [{"role": "user", "content": "这是生产环境数据库迁移脚本，帮我审查一遍安全性"}]
    assert classify(messages) == "l3_critical"


def test_tier_to_model_uses_default_when_no_override():
    result = tier_to_model("l1_daily", default_model="anthropic/claude-opus-4.6", tier_overrides={})
    assert result == "anthropic/claude-opus-4.6"


def test_tier_to_model_uses_override_when_configured():
    overrides = {"l2_deep": "anthropic/claude-opus-4.8"}
    result = tier_to_model("l2_deep", default_model="anthropic/claude-opus-4.6", tier_overrides=overrides)
    assert result == "anthropic/claude-opus-4.8"


def test_single_critical_keyword_alone_does_not_reach_l3():
    # 核心修复点：单独一个高危词不该直接拍板成最高档，只到l2_deep
    messages = [{"role": "user", "content": "这个数据库迁移方案是不是有问题"}]
    assert classify(messages) == "l2_deep"


def test_critical_keyword_plus_code_signal_reaches_l3():
    messages = [{"role": "user", "content": "生产环境的这段代码有bug需要debug"}]
    assert classify(messages) == "l3_critical"


def test_code_and_complex_signals_together_reach_l2_not_l3():
    messages = [{"role": "user", "content": "review这段代码的架构设计"}]
    assert classify(messages) == "l2_deep"


def test_accumulated_signals_without_critical_keyword_reach_l3():
    padding = "这段话是用来撑长度的填充文字。" * 10
    text = "需要重构这段代码并且同时调试\n第二行内容\n第三行内容\n" + padding
    messages = [{"role": "user", "content": text}]
    assert classify(messages) == "l3_critical"
