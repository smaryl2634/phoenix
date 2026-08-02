import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify.hallucination import evaluate_response


def _fake_client(content: str):
    """构造一个模仿 OpenAI SDK 响应形状的假客户端：
    client.chat.completions.create(...) -> 有 .choices[0].message.content 的对象。
    不依赖真实 openai 包。"""

    def create(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_low_tier_skips_verification_entirely():
    calls = []

    def get_client():
        calls.append(True)
        return (_fake_client("OK"), "verifier-model")

    result = evaluate_response("一些普通回复内容", "l1_daily", get_client)
    assert result is None
    assert calls == []  # 低档位根本不应该调用 get_client


def test_none_tier_skips_verification():
    result = evaluate_response("内容", None, lambda: (_fake_client("OK"), "verifier-model"))
    assert result is None


def test_high_tier_client_unavailable_degrades_to_allow():
    result = evaluate_response("内容", "l2_deep", lambda: (None, None))
    assert result is None


def test_high_tier_get_client_raises_degrades_to_allow():
    # get_text_auxiliary_client() 本身可能抛异常（配置解析失败等），不只是返回
    # (None, None) 这一种"不可用"的表现方式——两种都必须降级放行，不能让异常
    # 从 evaluate_response 里冒出去把用户卡住。
    def raising_get_client():
        raise RuntimeError("provider resolution failed")

    result = evaluate_response("内容", "l3_critical", raising_get_client)
    assert result is None


def test_high_tier_call_raises_degrades_to_allow():
    def raising_create(**kwargs):
        raise RuntimeError("network error")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=raising_create))
    )
    result = evaluate_response("内容", "l3_critical", lambda: (client, "verifier-model"))
    assert result is None


def test_high_tier_verdict_ok_returns_none():
    result = evaluate_response(
        "内容", "l2_deep", lambda: (_fake_client("OK"), "verifier-model")
    )
    assert result is None


def test_high_tier_verdict_issue_prepends_warning_preserves_original():
    result = evaluate_response(
        "原始回复内容一字不改",
        "l3_critical",
        lambda: (_fake_client("ISSUE: 这里的数字看起来是编造的"), "verifier-model"),
    )
    assert result is not None
    assert result.endswith("原始回复内容一字不改")
    assert "这里的数字看起来是编造的" in result
    assert result.startswith("⚠️")


def test_high_tier_verdict_lowercase_issue_still_recognized():
    # 核验模型不一定严格按大小写来，判断要 case-insensitive
    result = evaluate_response(
        "内容", "l2_deep", lambda: (_fake_client("issue: 看起来可疑"), "verifier-model")
    )
    assert result is not None
    assert "看起来可疑" in result


def test_verify_call_passes_a_bounded_timeout():
    # 阻塞式设计（用户等核验完再看到回复）必须有界——核验端点卡住时不能让用户
    # 等到 SDK 默认的~600秒超时才降级放行，call() 必须显式传 timeout。
    captured_kwargs = {}

    def create(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    evaluate_response("内容", "l2_deep", lambda: (client, "verifier-model"))
    assert "timeout" in captured_kwargs
    assert captured_kwargs["timeout"] <= 30


def test_high_tier_verdict_issue_with_fullwidth_colon_still_extracts_reason():
    # 核验模型是中文prompt，可能用全角冒号"："而不是ASCII冒号，两种都要能正确
    # 提取出理由部分，而不是把整个"ISSUE：..."原样堆进提示里。
    result = evaluate_response(
        "内容", "l3_critical", lambda: (_fake_client("ISSUE：看起来像编造的数据"), "verifier-model")
    )
    assert result is not None
    assert "看起来像编造的数据" in result
    assert "ISSUE" not in result.split("---")[0]


# Tests for cheap_pre_check
from verify.hallucination import cheap_pre_check


def test_cheap_pre_check_empty_response():
    assert cheap_pre_check("") == "回复为空"
    assert cheap_pre_check("   ") == "回复为空"


def test_cheap_pre_check_refusal_pattern():
    result = cheap_pre_check("抱歉，我不能帮助你完成这个请求")
    assert result is not None
    assert "拒答" in result


def test_cheap_pre_check_uncertainty_pattern_short_response():
    result = cheap_pre_check("这个我不确定")
    assert result is not None


def test_cheap_pre_check_uncertainty_pattern_long_response_not_flagged():
    # 长回复里出现"不确定"这个词，很可能只是在讨论"不确定性"这个概念本身，
    # 不该被误判——只有短回复+不确定关键词才算"疑似答非所问"
    long_text = "关于这个系统设计中的不确定性因素，" + "详细分析内容。" * 40
    assert cheap_pre_check(long_text) is None


def test_cheap_pre_check_refusal_pattern_long_response_not_flagged():
    # 最终整分支复审发现的Minor问题：_REFUSAL_PATTERNS 原来没有长度护栏，
    # 长回复里随便哪里出现"我不能"三个字（比如在讨论某个技术限制本身）就会被
    # 误判成"疑似拒答"，直接跳过后续真正的付费核验——这个方向的误判比
    # _UNCERTAINTY_PATTERNS 更危险（后者误判只是"多疑心"，前者误判是"该核验的
    # 没核验"）。要跟不确定关键词用同一条<200字护栏。
    long_text = (
        "这个系统设计中有一个技术限制：单个节点我不能同时处理超过一万个并发连接，"
        + "详细分析内容。" * 40
    )
    assert cheap_pre_check(long_text) is None


def test_cheap_pre_check_normal_response_passes():
    assert cheap_pre_check("一致性哈希的核心实现思路是这样的：先构造一个虚拟节点环...") is None


def test_high_tier_pre_check_catches_empty_response_without_calling_client():
    calls = []

    def get_client():
        calls.append(True)
        return (_fake_client("OK"), "verifier-model")

    result = evaluate_response("", "l2_deep", get_client)
    assert result is not None
    assert "回复为空" in result
    assert calls == []  # 预检直接拦下，不该花钱调核验


def test_high_tier_pre_check_passes_still_triggers_real_verification():
    # 防回归关键测试：预检没抓到问题，绝对不能演变成"直接放行不核验"，
    # 必须照常走原有的付费核验路径
    calls = []

    def get_client():
        calls.append(True)
        return (_fake_client("OK"), "verifier-model")

    result = evaluate_response("一致性哈希的核心实现思路是这样的", "l2_deep", get_client)
    assert result is None
    assert calls == [True]  # 预检通过后，付费核验必须被真实调用过
