"""隐私提醒文案——精确文本，用户明确要求"怎么切过去"和"记得切回来"必须在
同一段话里说清楚，不能只说一半。逐字使用，不要改写。"""
from __future__ import annotations

PRIVACY_WARNING_TEXT = (
    "检测到本轮内容可能涉及敏感/隐私信息。\n\n"
    "如果需要用本地模型处理（数据不出网），请手动运行：\n"
    "  /model turbofieldfare\n\n"
    "注意：这次切换是手动的，不会自动切回云端——等你需要用到云端模型的能力时\n"
    "（比如更强的推理），同样需要自己运行 /model <你的云端模型名> 切换回去，\n"
    "不死鸟不会替你自动切回。"
)


def append_privacy_warning(response_text: str) -> str:
    return f"{response_text}\n\n{PRIVACY_WARNING_TEXT}"
