"""存档点提醒判定——检测高危工具调用且用户没开 Hermes 自带的 checkpoint/rollback
功能时，事后提醒用户去开。判定"这次调用算不算高危"直接复用 Hermes 自己判断
"要不要打 checkpoint" 的同一套标准，不重新发明。"""
from __future__ import annotations

from pathlib import Path

import yaml

CHECKPOINT_REMINDER_TEXT = (
    "🎮 即将执行高危操作——就像游戏里踩雷之前的存档点，现在还来得及。\n\n"
    "Hermes 自带\"存档\"功能（读档就是 /rollback），默认是关的。开一下：\n"
    "  hermes chat --checkpoints\n\n"
    "开完之后，每次干\"删/改\"这种活之前会自动帮你偷偷存一档，\n"
    "翻车了直接读档，不用自己肉身手动回滚。\n\n"
    "本次操作已放行，下次建议先开 checkpoints 再执行高危操作。"
)

_CHECKPOINT_FILE_TOOLS = {"write_file", "patch"}


def is_checkpoint_triggering_call(tool_name: str, args: dict) -> bool:
    """判断这次工具调用是不是 Hermes 自己会拿去打 checkpoint 的那类——跟
    agent/tool_executor.py 里 CheckpointManager 的真实触发条件保持一致：
    write_file/patch 两个文件工具，或者 terminal 工具里被判定为"破坏性"的命令。

    import Hermes 内部函数失败（未来版本可能挪了位置/改了签名）时保守返回
    False，不阻断不死鸟其它功能——这是安静降级，不是硬依赖。"""
    if tool_name in _CHECKPOINT_FILE_TOOLS:
        return True
    if tool_name == "terminal":
        command = args.get("command", "")
        if not command:
            return False
        try:
            from agent.tool_dispatch_helpers import _is_destructive_command
        except Exception:
            return False
        try:
            return bool(_is_destructive_command(command))
        except Exception:
            return False
    return False


def is_checkpoints_enabled(path: Path | None = None) -> bool:
    """读取 Hermes 根配置 checkpoints.enabled 字段，跟 __init__.py 里
    _load_primary_provider() 是同一种"直接读 YAML 文件"模式。读取失败（文件
    不存在/格式错误/字段缺失）一律返回 False——保守到"提醒"这一侧：宁可多提醒
    一次（低成本），也不能因为读取失败误判成"已经开启"从而漏掉真正该提醒的
    场景。"""
    target = path
    if target is None:
        from hermes_constants import get_hermes_home
        target = get_hermes_home() / "config.yaml"
    if not target.exists():
        return False
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    checkpoints_cfg = data.get("checkpoints")
    if not isinstance(checkpoints_cfg, dict):
        return False
    return bool(checkpoints_cfg.get("enabled", False))
