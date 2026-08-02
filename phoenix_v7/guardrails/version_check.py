"""读取当前运行的 Hermes Agent 版本，跟不死鸟最近一次真实核实过的版本号比较——
为 GitHub 公开发布准备，用户装在自己电脑上各种版本的 Hermes 上，需要知道"这个版本
不死鸟真的核实过吗"。

进程内直接 `from hermes_cli import __version__` 读取，不 shell out 执行
`hermes --version`——跟 __init__.py::_load_primary_provider() 读 config.yaml
是同一种"直接 import Hermes 内部模块"的手法。"""
from __future__ import annotations


def _read_hermes_version() -> str | None:
    """读取当前运行的 Hermes Agent 版本号。导入失败（未来 Hermes 可能移除/重命名
    这个属性）一律返回 None，不能让这个信息性功能本身导致 phoenix-status 报错崩掉。"""
    try:
        from hermes_cli import __version__
        return __version__
    except Exception:
        return None


def _parse_version(version: str) -> tuple[int, ...] | None:
    """把 "0.19.1" 这种三段点分字符串（可能带 v 前缀）拆成整数元组，格式不对
    （未来版本号规则变了）返回 None，交给调用方降级处理，不抛异常。"""
    try:
        stripped = version.strip().lstrip("vV")
        if not stripped:
            return None
        return tuple(int(p) for p in stripped.split("."))
    except Exception:
        return None


def check_hermes_compatibility(verified_version: str) -> str:
    """返回 "match" / "newer" / "older" / "unknown" 之一。
    "unknown" 覆盖：读不到当前版本、版本格式解析失败两种情况——不细分，调用方
    只需要知道"没法给出明确结论"就够了。"""
    running = _read_hermes_version()
    if running is None:
        return "unknown"
    running_tuple = _parse_version(running)
    verified_tuple = _parse_version(verified_version)
    if running_tuple is None or verified_tuple is None:
        return "unknown"
    if running_tuple == verified_tuple:
        return "match"
    return "newer" if running_tuple > verified_tuple else "older"
