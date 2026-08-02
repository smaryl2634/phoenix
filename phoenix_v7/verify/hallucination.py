"""transform_llm_output 钩子的核验逻辑。只核验高危档位（l2_deep/l3_critical）的
回复，用 Hermes 原生的 get_text_auxiliary_client() 直接发起一次独立的核验调用——
不走 Loop 那套子Agent委派机制（agent/subagent_lifecycle.py），因为这里没有"重试"
的场景：transform_llm_output 触发时这一轮对话已经结束、回复已经生成，不像
pre_tool_call 那样可以拦下来等模型自己决定要不要重试。直接同步调用一个独立的
辅助模型更合适、更轻。

核验通道本身不可用（get_client() 返回 (None, None)）或调用失败（网络错误等）一律
降级为不拦截，返回 None——这是个"锦上添花"的核验层，不是安全防线（安全防线是已有
的熔断器/审批闸），核验机制本身故障不应该阻断正常使用。"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger("phoenix_v7")

_HIGH_TIERS = ("l2_deep", "l3_critical")

_VERIFY_SYSTEM_PROMPT = (
    "你是一个严格的事实核验员。下面是另一个AI助手刚生成的回复。"
    "判断这段回复里的关键结论/事实性陈述是否有明显编造、缺乏依据、"
    "或者过度确定的地方。如果发现问题，用一行文字说明具体是哪里、"
    "为什么可疑，开头写\"ISSUE:\"。如果没有发现明显问题，只回复"
    "\"OK\"这一个词，不要写别的。"
)

_REFUSAL_PATTERNS = ("我不能", "无法帮助", "无法提供", "i cannot", "i'm unable to")
_UNCERTAINTY_PATTERNS = ("不确定", "不知道", "无法判断", "i don't know", "i'm not sure")


def cheap_pre_check(response_text: str) -> str | None:
    """纯规则、不调用模型的免费预检。返回具体问题描述字符串就是抓到明显问题了；
    返回 None 代表预检没抓到问题——**不代表回复没有幻觉**，只代表没有"明显烂"这类
    问题，真正的语义核验（下面 evaluate_response 里的付费调用）照常执行，预检
    不能替代它，这是本函数存在的唯一边界，不要在这个函数里加任何"看起来没问题就
    跳过后续核验"的逻辑——那属于调用方 evaluate_response 的职责。"""
    text = (response_text or "").strip()
    if not text:
        return "回复为空"
    if len(text) < 200 and any(p in text for p in _REFUSAL_PATTERNS):
        return "回复疑似拒答"
    if len(text) < 200 and any(p in text for p in _UNCERTAINTY_PATTERNS):
        return "回复疑似不确定/答非所问"
    return None


def evaluate_response(
    response_text: str,
    tier: str | None,
    get_client: Callable[[], tuple],
) -> str | None:
    if tier not in _HIGH_TIERS:
        return None

    pre_check_issue = cheap_pre_check(response_text)
    if pre_check_issue is not None:
        return f"⚠️ [phoenix_v7 幻觉核验] {pre_check_issue}\n\n---\n\n{response_text}"

    try:
        client, model = get_client()
    except Exception as exc:
        logger.warning("phoenix_v7 hallucination-check get_client() failed: %s", exc)
        return None
    if client is None or model is None:
        return None

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": response_text},
            ],
            max_tokens=200,
            # 这是个阻塞式设计（用户等核验完再看到回复），但阻塞时长必须有界——
            # 核验端点卡住时不能让用户等到SDK默认的~600秒超时才降级放行。
            timeout=20,
        )
        verdict = (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("phoenix_v7 hallucination-check call failed: %s", exc)
        return None

    if verdict.upper().startswith("ISSUE"):
        import re

        parts = re.split(r"[:：]", verdict, maxsplit=1)
        reason = parts[1].strip() if len(parts) == 2 else verdict
        return f"⚠️ [phoenix_v7 幻觉核验] {reason}\n\n---\n\n{response_text}"
    return None
