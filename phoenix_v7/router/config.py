"""tier_overrides 配置文件读取，默认路径是不死鸟插件目录下的 config/tiers.json.

2026-07-28状态说明：当前这份配置是空字典 {}，是刻意留空，不是漏填。含义是——
classify()/tier_to_model() 这套"判断该用哪个档位"的逻辑照常运行、照常在日志里打印
tier=xxx，但因为没有任何档位配了对应模型，tier_to_model() 会一直落到 fallback（也就是
Hermes当前配置的默认模型），实际不会发生模型切换。这是用户在2026-07-28真机验收后明确
选择的过渡状态（"先不区分，只保留判断能力，风险更低"），不要在没有明确讨论过的情况下
自己往这里填模型名——填了就会真的开始按档位切模型，是一个有实际影响的产品决策，需要
用户确认要切哪些档位、切成什么模型。

2026-07-28（续，V7.1）：加了 enabled 开关，格式从纯 {tier: model} 平铺字典升级成
{"enabled": bool, "tiers": {tier: model}}。旧格式（含空字典 {}）继续兼容，读到旧格式
时 enabled 按 True 处理——但因为旧格式下 tiers 多半是空的，效果上跟"关闭"是一样的，
不会有任何用户因为这次升级突然被动"开启"了什么本来没配置过的东西。"""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "tiers.json"


def load_tier_overrides(path: Path | None = None) -> tuple[bool, dict[str, str | list[str]]]:
    """返回 (enabled, tier_overrides)。

    新格式 {"enabled": bool, "tiers": {...}} 按字面读取。旧格式（纯 {tier: model}
    平铺字典，包括空字典）enabled 固定按 True 处理——旧格式没有 enabled 这个概念，
    这不是"猜"，是刻意选择跟旧行为完全等价的默认值。
    """
    target = path or _CONFIG_PATH
    if not target.exists():
        return True, {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return True, {}
    if not isinstance(data, dict):
        return True, {}
    if "enabled" in data and "tiers" in data:
        enabled = bool(data.get("enabled", True))
        tiers = data.get("tiers")
        if not isinstance(tiers, dict):
            tiers = {}
        return enabled, {k: v for k, v in tiers.items() if _is_valid_tier_value(v)}
    # 旧格式：纯 {tier: model} 平铺字典
    return True, {k: v for k, v in data.items() if _is_valid_tier_value(v)}


def _is_valid_tier_value(value) -> bool:
    """一个档位配的值合法当且仅当：单个模型字符串，或者一份纯字符串候选链列表。

    2026-07-29修正：这个过滤器最早只认字符串，V6.1机制移植加入候选链（列表）
    格式后没有同步更新，导致列表值被静默丢弃——Task 4 真机验证时才发现
    resolve_candidate() 永远收不到候选链，因为 load_tier_overrides() 在它之前
    就已经把列表值滤掉了。"""
    if isinstance(value, str):
        return True
    if isinstance(value, list):
        return bool(value) and all(isinstance(m, str) for m in value)
    return False


def write_enabled(enabled: bool, path: Path | None = None) -> None:
    """改写 enabled 字段，保留（并在需要时升级）已有的 tiers 映射表。

    遇到旧格式（纯 {tier: model} 平铺字典，或文件不存在）时，把已有的 tier 映射
    原样搬进新格式的 "tiers" 字段，不丢用户已经填好的配置。
    """
    target = path or _CONFIG_PATH
    data: dict = {}
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}

    if "tiers" not in data or not isinstance(data.get("tiers"), dict):
        old_tiers = {k: v for k, v in data.items() if isinstance(v, str)}
        data = {"tiers": old_tiers}

    data["enabled"] = enabled
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_candidate(
    tier_override: str | list[str] | None,
    default_model: str,
    health,
) -> str:
    """把 tiers.json 里某个档位的配置值（字符串=单模型，列表=候选链，
    None=没配这档）解析成实际要用的模型字符串。

    字符串格式完全不触碰健康追踪——单模型用户没有候选链可言，这条路径必须
    零开销、零新增故障面。列表格式才会调用 health.ordered_candidates() 挑
    链里最健康的排第一个。"""
    if tier_override is None:
        return default_model
    if isinstance(tier_override, str):
        return tier_override
    if not tier_override:
        return default_model
    ordered = health.ordered_candidates(tier_override)
    return ordered[0]
