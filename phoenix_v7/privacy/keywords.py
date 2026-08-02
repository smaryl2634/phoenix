"""隐私敏感词检测——初版基础词表，YAGNI，不追求完美覆盖，后续按真实误报/漏报
情况迭代。跟 router/metis_core.py::classify() 是同一种"取最新一条 user 消息"
判断模式，签名故意保持一致，方便 _route() 里并列调用。"""
from __future__ import annotations

import re

_ID_CARD_RE = re.compile(r"\d{17}[\dXx]")
_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_KEYWORD_TERMS = ("密码", "password", "银行卡", "卡号")


def detect_sensitive(messages: list[dict]) -> bool:
    """返回最新一条 user 消息是否命中隐私敏感词/模式。"""
    last_user = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = str(msg.get("content", ""))
            break

    if not last_user:
        return False
    if _ID_CARD_RE.search(last_user):
        return True
    if _PHONE_RE.search(last_user):
        return True
    lowered = last_user.lower()
    if any(term.lower() in lowered for term in _KEYWORD_TERMS):
        return True
    return False
