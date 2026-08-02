"""本地 turbofieldfare provider 的共用安全阀——token 数预检 + 目标识别。

两个用途共用同一套检查逻辑（隐私路由 / 欠费兜底升级），检查的是"这个请求发给
本地这个26B模型安不安全"，跟"为什么想发给它"无关。

已知架构限制：这里的"安全"判定只能做到记录/日志，不能做到真正拦截重定向——
llm_request 中间件（_route() 所在）只能改写 request.model 等请求体字段，
不能切换 provider/base_url（那绑定在 agent 对象本身，只有 Hermes 自己的
try_activate_fallback() 能做到，没有给插件调用设计的公开接口）。所以
check_local_provider_safety() 返回 False 时，调用方只能记日志提醒，不能
真的把请求改道到别的 provider。"""
from __future__ import annotations

import platform

TURBOFIELDFARE_PROVIDER = "turbofieldfare"

# 4096 声明 context_length 打八折留余量，不是拍脑袋的数字。
SAFE_TOKEN_LIMIT = 3277

_CHARS_PER_TOKEN = 4


def is_turbofieldfare_supported_platform(system_name: str | None = None) -> bool:
    """turbofieldfare 本地引擎是基于苹果 MLX 框架编译的，只能跑 Apple Silicon。
    Windows/Linux 用户装了不死鸟也不可能真的用上这个功能——真实事故：Windows
    用户装完 v7.5.0 看到隐私提醒引导他们运行 /model turbofieldfare，跟着做了
    但这个 provider 在他们的平台上根本不可能存在，白白制造困惑。任何要"建议
    用户切到本地模型"的地方，先过这道判断。"""
    name = system_name if system_name is not None else platform.system()
    return name == "Darwin"


def is_turbofieldfare_target(model: str, provider: str) -> bool:
    """判断这次请求的目标是不是本地 turbofieldfare。

    优先按 provider 精确匹配（_route() 的 context 里可靠地带 provider 字段）；
    model 里出现 "turbofieldfare" 子串作为兜底信号，兼容某些调用路径 model
    字符串本身带 provider 前缀的情况。"""
    if provider == TURBOFIELDFARE_PROVIDER:
        return True
    return TURBOFIELDFARE_PROVIDER in (model or "")


def estimate_tokens(messages: list[dict]) -> int:
    """粗估 token 数：所有消息内容字符数之和 // 4。不引入 tiktoken 这种重依赖，
    这是个安全阀预检，不需要精确计费级别的准确度。

    只要存在非空字符串内容，至少估算为 1 token（避免极短消息被算成 0 token
    而绕过后续判断）；完全没有字符串内容时才返回 0。"""
    total_chars = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
    if total_chars == 0:
        return 0
    return max(1, total_chars // _CHARS_PER_TOKEN)


def check_local_provider_safety(messages: list[dict]) -> tuple[bool, str | None]:
    """(是否安全, 拒绝原因)。超过 SAFE_TOKEN_LIMIT 判定不安全——真机验证过的结论：
    非流式超长请求本地服务器至少干净报 400，流式超长请求会断连吐半截数据，
    这条预检是为了提前发现"这次不适合走本地"，不是真的能拦截（见模块docstring）。"""
    estimated = estimate_tokens(messages)
    if estimated > SAFE_TOKEN_LIMIT:
        return False, f"预估 {estimated} tokens，超过本地模型安全阈值 {SAFE_TOKEN_LIMIT}"
    return True, None
