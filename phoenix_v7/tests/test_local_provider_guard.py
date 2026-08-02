import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.local_provider_guard import (
    TURBOFIELDFARE_PROVIDER,
    SAFE_TOKEN_LIMIT,
    is_turbofieldfare_supported_platform,
    is_turbofieldfare_target,
    estimate_tokens,
    check_local_provider_safety,
)


def test_turbofieldfare_provider_constant():
    assert TURBOFIELDFARE_PROVIDER == "turbofieldfare"


def test_is_turbofieldfare_supported_platform_true_on_macos():
    assert is_turbofieldfare_supported_platform("Darwin") is True


def test_is_turbofieldfare_supported_platform_false_on_windows():
    assert is_turbofieldfare_supported_platform("Windows") is False


def test_is_turbofieldfare_supported_platform_false_on_linux():
    assert is_turbofieldfare_supported_platform("Linux") is False


def test_is_turbofieldfare_supported_platform_defaults_to_real_platform_system():
    import platform as _platform

    assert is_turbofieldfare_supported_platform() == (_platform.system() == "Darwin")


def test_is_turbofieldfare_target_matches_by_provider():
    assert is_turbofieldfare_target("gemma-4-26b-a4b-it", "turbofieldfare") is True


def test_is_turbofieldfare_target_matches_by_model_substring():
    assert is_turbofieldfare_target("turbofieldfare/gemma-4-26b-a4b-it", "") is True


def test_is_turbofieldfare_target_false_for_other_provider():
    assert is_turbofieldfare_target("z-ai/glm-5.2", "nous") is False


def test_is_turbofieldfare_target_false_for_empty_input():
    assert is_turbofieldfare_target("", "") is False


def test_estimate_tokens_short_message():
    messages = [{"role": "user", "content": "在吗"}]
    assert estimate_tokens(messages) == max(1, len("在吗") // 4)


def test_estimate_tokens_sums_all_messages():
    messages = [
        {"role": "system", "content": "a" * 40},
        {"role": "user", "content": "b" * 40},
    ]
    assert estimate_tokens(messages) == 20  # (40+40)//4


def test_estimate_tokens_ignores_non_string_content():
    messages = [{"role": "user", "content": None}]
    assert estimate_tokens(messages) == 0


def test_check_local_provider_safety_short_request_passes():
    messages = [{"role": "user", "content": "帮我写一句话"}]
    safe, reason = check_local_provider_safety(messages)
    assert safe is True
    assert reason is None


def test_check_local_provider_safety_over_limit_rejects():
    # SAFE_TOKEN_LIMIT * 4 + 一点余量的字符数，确保估算结果超过阈值
    long_content = "字" * ((SAFE_TOKEN_LIMIT + 10) * 4)
    messages = [{"role": "user", "content": long_content}]
    safe, reason = check_local_provider_safety(messages)
    assert safe is False
    assert reason is not None
    assert str(SAFE_TOKEN_LIMIT) in reason


def test_check_local_provider_safety_exact_boundary_passes():
    content = "字" * (SAFE_TOKEN_LIMIT * 4)
    messages = [{"role": "user", "content": content}]
    safe, _reason = check_local_provider_safety(messages)
    assert safe is True


def test_check_local_provider_safety_one_over_boundary_rejects():
    content = "字" * ((SAFE_TOKEN_LIMIT + 1) * 4)
    messages = [{"role": "user", "content": content}]
    safe, _reason = check_local_provider_safety(messages)
    assert safe is False
