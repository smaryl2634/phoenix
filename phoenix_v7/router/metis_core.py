"""Metis V6 复杂度分类 —— 加权计分版本，2026-07-29 从 V6.1 真实源码
（metis_v6_core.py 的 _complexity_score）移植并改良：V6.1 原版 l3_critical 这档
仍然是单关键词直接拍板，这次连 l3 也一起上加权计分，避免"一个高危词就把整个
对话判成最高危险档"这种误伤（2026-07-28 用户明确反馈过 5.2/5.3 时期因为纯关键词
判断出过真实问题）。

四档：l0_fast（打招呼/极短消息）/ l1_daily（日常问答，默认档）/
l2_deep（需要设计/分析/重构类深度工作）/ l3_critical（生产环境/安全/数据库等高风险操作）。

阈值 L2_THRESHOLD=3 / L3_THRESHOLD=7 是宽松保守初值，不是精确校准过的数字，
后续用真实使用数据校准。**但改之前先看 tests/test_metis_core.py**——
test_critical_keyword_is_l3_critical 这条测试的分数刚好卡在 7 分这个边界上，
改阈值前先确认不会静默改坏这条已有测试。"""
from __future__ import annotations

import re

_CRITICAL_KEYWORDS = (
    "生产环境", "生产库", "数据库迁移", "线上", "安全审查",
    "删除", "不可逆", "密钥", "prod", "production",
)
_CODE_KEYWORDS = ("debug", "调试", "review", "审查", "代码", "bug", "报错")
_COMPLEX_KEYWORDS = ("设计", "架构", "重构", "深入分析")
_CONNECTOR_RE = re.compile(r"(?:并|然后|同时|还要|再|以及)")

_L3_THRESHOLD = 7
_L2_THRESHOLD = 3
_L0_MAX_CHARS = 6


def _complexity_score(text: str) -> int:
    score = 0
    if any(kw in text for kw in _CRITICAL_KEYWORDS):
        score += 5
    if any(kw in text for kw in _CODE_KEYWORDS):
        score += 2
    if any(kw in text for kw in _COMPLEX_KEYWORDS):
        score += 3
    if len(text) > 160:
        score += 1
    if text.count("\n") >= 3:
        score += 1
    if len(_CONNECTOR_RE.findall(text)) >= 2:
        score += 1
    return score


def classify(messages: list[dict]) -> str:
    """返回最新一条 user 消息对应的档位."""
    last_user = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = str(msg.get("content", ""))
            break

    score = _complexity_score(last_user)
    if score >= _L3_THRESHOLD:
        return "l3_critical"
    if score >= _L2_THRESHOLD:
        return "l2_deep"
    if len(last_user.strip()) <= _L0_MAX_CHARS:
        return "l0_fast"
    return "l1_daily"


def tier_to_model(tier: str, default_model: str, tier_overrides: dict[str, str]) -> str:
    """把档位映射成实际要用的 model 字符串.

    tier_overrides 是用户自己在 config 里配的"这个档位该用哪个模型"，没配就用
    Hermes 当前已经配好的 default_model —— 保证只有一个模型的用户（"三种小伙伴"里的
    第二种）插件行为等同于不路由，不会因为没配置候选模型池就报错或空转。
    """
    return tier_overrides.get(tier, default_model)
