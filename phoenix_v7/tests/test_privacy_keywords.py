import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privacy.keywords import detect_sensitive


def test_detect_sensitive_phone_number():
    messages = [{"role": "user", "content": "帮我记一下这个号码13812345678"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_id_card_18_digits():
    messages = [{"role": "user", "content": "身份证号440101199001011234"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_id_card_with_x_suffix():
    messages = [{"role": "user", "content": "身份证是44010119900101123X"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_password_keyword():
    messages = [{"role": "user", "content": "我的密码是abc123，帮我看看安全吗"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_password_keyword_english():
    messages = [{"role": "user", "content": "my password is abc123"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_bank_card_keyword():
    messages = [{"role": "user", "content": "银行卡号是多少来着"}]
    assert detect_sensitive(messages) is True


def test_detect_sensitive_no_hit_returns_false():
    messages = [{"role": "user", "content": "今天天气怎么样"}]
    assert detect_sensitive(messages) is False


def test_detect_sensitive_only_checks_latest_user_message():
    messages = [
        {"role": "user", "content": "我的密码是abc123"},
        {"role": "assistant", "content": "好的"},
        {"role": "user", "content": "今天天气怎么样"},
    ]
    assert detect_sensitive(messages) is False


def test_detect_sensitive_empty_messages_returns_false():
    assert detect_sensitive([]) is False


def test_detect_sensitive_ignores_non_user_roles():
    messages = [{"role": "system", "content": "身份证440101199001011234"}]
    assert detect_sensitive(messages) is False
