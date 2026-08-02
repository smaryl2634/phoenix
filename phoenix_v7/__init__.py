"""Phoenix V7 - Hermes Agent 插件.

最小核心：路由分档 / 成本与风险防线 / 自愈。
全部通过 Hermes 官方 middleware 接入，不修改任何 Hermes 核心文件。
"""
from __future__ import annotations

import logging
import yaml
from pathlib import Path

from hermes_constants import get_hermes_home

from .router.metis_core import classify
from .router.config import load_tier_overrides, write_enabled, resolve_candidate
from .guardrails.cost_monitor import CostMonitor
from .guardrails.circuit_breaker import CircuitBreaker
from .guardrails.model_health import ModelHealthTracker
from .guardrails.loop_signal import (
    _is_goal_active, _goal_created_at, _is_checklist_seeded, _mark_checklist_seeded,
)
from .guardrails.version_check import _read_hermes_version, check_hermes_compatibility
from .verify.hallucination import evaluate_response as _evaluate_hallucination
from .guardrails.tool_guard import (
    evaluate as _evaluate_tool_guard,
    evaluate_loop_checklist_gate as _evaluate_loop_checklist_gate,
)
from agent.auxiliary_client import get_text_auxiliary_client
from .selfheal.antibody import AntibodyLibrary
from .selfheal.error_processor import ErrorProcessor

logger = logging.getLogger("phoenix_v7")

# session_id -> 最近一次路由判定的档位。Task 6 的 pre_tool_call 钩子读这份状态，判断
# "这一轮是不是高危档位，工具调用前要不要转人工审批"。进程内内存字典足够——重启插件
# （= 重启 hermes 进程）后清空是可接受的行为，不需要持久化。
_last_tier_by_session: dict[str, str] = {}

# session_id -> 这个session下一次API调用实际会用的模型（_route()每次被调用都刷新，
# 不管有没有真的换过）。最终整分支复审发现的真bug：_record_usage/_record_api_error
# 原本直接用 context.get("model")，那个值是 Hermes 的 agent.model——路由前的默认模型，
# _route() 换模型只改写了发出去的 request payload，从不回写 agent.model 本身。结果
# 健康追踪的成功/失败信号永远记在"没被真正调用过的模型"名下，候选链健康感知形同虚设
# （安全地退化成"永远选第一个候选"，不会锁死用户，但功能是死的）。这份字典就是记录
# "这个session这一轮真正会打给谁"，_record_usage/_record_api_error 优先读它。
_resolved_model_by_session: dict[str, str] = {}

_STATE_DIR = Path(__file__).resolve().parent / "state"
# 2026-07-28修正：_cost_monitor 不再用来挡任何工具调用（原来 is_over_limit() 基于
# _USD_PER_1K_TOKENS 这个纯靠猜的费率，不对应任何具体模型真实计费，是2026-07-28那次
# 真机事故——熔断/成本上限跳闸后无差别锁死全部工具且无自救手段——的根源之一。用户复盘
# 后明确要求去掉这条基于猜测数字的拦截，只保留下面基于真实API报错次数的熔断器）。
# 仍然保留被动记账，写进 state/cost.json 供用户自己回头看开销趋势参考，不再有任何
# 阻断工具调用的效力。
_cost_monitor = CostMonitor(storage_path=_STATE_DIR / "cost.json")
_breaker = CircuitBreaker(failure_threshold=3, reset_after_seconds=300)
_model_health = ModelHealthTracker()
_USD_PER_1K_TOKENS = 0.002  # 粗估，仅供参考，不对应任何具体模型真实计费，不用于拦截判断
_antibody = AntibodyLibrary(storage_path=_STATE_DIR / "antibody.json")
_error_processor = ErrorProcessor(antibody=_antibody)

# session_id -> 是否有一次评判子Agent对这个session当前待执行的高危操作给出"通过"结论，
# 单次有效（_guard_tool 读到后立刻消费掉，不会重复放行）。V1已知限制：无法区分"这是
# 我方才提示模型委派的评判子Agent"还是"模型出于别的原因委派的某个无关子Agent"——只要
# child_summary 恰好以 APPROVED 开头就会被记成一次有效批准，触发条件很窄，V1接受这个
# 风险，不在这版加更严格的匹配（那需要不死鸟介入委派prompt编写，违反"不直接编排子Agent
# 调用"的设计原则）。
_pending_loop_approvals: dict[str, bool] = {}

_HERMES_CONFIG_PATH = get_hermes_home() / "config.yaml"


def _load_primary_provider(path: Path | None = None) -> str:
    """读取 Hermes 根配置 model.provider，用来判断当前这次请求是不是走的主线路。

    Hermes 官方 fallback_model 链激活时，重试请求的 context["provider"] 会变成
    fallback 条目自己的 provider（不再是主 provider）——_route() 需要知道这件事，
    不然会在重试请求上again按档位把模型改回云端主力模型，抵消掉 Hermes 刚做的切换。
    读取失败（文件不存在/格式错误/字段缺失）返回空字符串，调用方把空字符串当作
    "跳过这项检查"处理，不能因为读配置失败就让每次请求都被误判成"不在主线路上"。
    """
    target = path or _HERMES_CONFIG_PATH
    if not target.exists():
        return ""
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    model_cfg = data.get("model")
    if not isinstance(model_cfg, dict):
        return ""
    provider = model_cfg.get("provider")
    return provider if isinstance(provider, str) else ""


_primary_provider = _load_primary_provider()

_PLUGIN_YAML_PATH = Path(__file__).resolve().parent / "plugin.yaml"


def _read_verified_hermes_version(path: Path | None = None) -> str | None:
    """读取 plugin.yaml 的 verified_hermes_version 字段——跟
    _load_primary_provider() 读 config.yaml 是同一种"直接读 YAML 文件"模式。
    读取失败（文件不存在/格式错误/字段缺失）返回 None，调用方降级成"无法读取"。"""
    target = path or _PLUGIN_YAML_PATH
    if not target.exists():
        return None
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("verified_hermes_version")
    return version if isinstance(version, str) else None


def _route(request: dict, **context) -> dict | None:
    current_provider = context.get("provider") or ""
    if _primary_provider and current_provider and current_provider != _primary_provider:
        # 已经在 Hermes 的备用线路上，不死鸟不插手。这里提前 return 会跳过下面
        # _last_tier_by_session 的写入——是故意的：_guard_tool() 读不到 tier 时按
        # tier=None 处理，不会命中任何高危档位审批门槛，在降级状态下这是期望行为，
        # 不是遗漏。
        return None
    messages = request.get("messages") or context.get("conversation_history") or []
    tier = classify(messages)
    session_id = context.get("session_id", "")
    if session_id:
        _last_tier_by_session[session_id] = tier

    default_model = request.get("model", "")
    enabled, overrides = load_tier_overrides()
    if not enabled:
        if session_id:
            _resolved_model_by_session[session_id] = default_model
        return None  # 手动挡：档位判断/状态记录照常，但不介入模型选择

    tier_override = overrides.get(tier)
    new_model = resolve_candidate(tier_override, default_model, _model_health)
    if session_id:
        _resolved_model_by_session[session_id] = new_model
    if new_model == default_model:
        return None  # 没变化就不用返回替换，减少 trace 噪音
    new_request = dict(request)
    new_request["model"] = new_model
    logger.info("phoenix_v7 router: tier=%s model %s -> %s", tier, default_model, new_model)
    return {"request": new_request, "source": "phoenix_v7", "reason": f"tier={tier}"}


def _guard_tool(tool_name: str, args: dict, **context) -> dict | None:
    # 2026-07-28修正：不再用 _cost_monitor.is_over_limit(...) 的估算数字去挡工具调用
    # （那个费率是猜的，不是真实计费，是昨天事故的根源）。只看熔断器（基于真实API报错
    # 次数，更可信）。_cost_monitor 仍然在 _record_usage 里被动记账，供用户自己回头看
    # 开销趋势，只是不再拿它挡任何东西。
    session_id = context.get("session_id", "")
    tier = _last_tier_by_session.get(session_id)
    # Hermes 原生 cron 调度器给它触发的会话分配 "cron_<job_id>_..." 这样的
    # session_id（hermes-agent/cron/scheduler.py），不用不死鸟自己发明"这是调度
    # 触发的"新信号，直接检测这个既有前缀。
    is_scheduled = session_id.startswith("cron_")

    is_loop_active = _is_goal_active(session_id)
    goal_created_at = _goal_created_at(session_id) if is_loop_active else None
    checklist_seeded = (
        _is_checklist_seeded(session_id, goal_created_at)
        if is_loop_active and goal_created_at is not None
        else False
    )
    if is_loop_active:
        checklist_directive = _evaluate_loop_checklist_gate(
            tool_name, is_loop_active, checklist_seeded
        )
        if checklist_directive is not None:
            logger.info(
                "phoenix_v7 loop: tool=%s directive=%s", tool_name, checklist_directive["action"]
            )
            return checklist_directive

    directive = _evaluate_tool_guard(
        tier, _breaker.allow(), tool_name=tool_name, is_scheduled=is_scheduled,
        is_loop_active=is_loop_active,
    )
    if (
        directive is not None
        and directive.get("rule_key") == "phoenix_v7_loop_high_tier_needs_evaluator"
        and _pending_loop_approvals.pop(session_id, False)
    ):
        logger.info("phoenix_v7 loop: evaluator approval consumed, allowing tool=%s", tool_name)
        directive = None

    # 只有这次调用最终判定为"放行"，才把 todo 记成"已经真正执行了一次种 checklist 的
    # 调用"。此前的 bug：seeded 标记在 _evaluate_tool_guard 判定之前就打上了——如果这次
    # todo 调用本身被高危档位挡下（评判子 Agent 还没批准），checklist 实际从未被真正
    # seed 过，却已经被标记成"seeded"，导致这个 loop 的 checklist gate 永久失效（评判
    # 拒绝时尤其明显）。
    if (
        directive is None
        and is_loop_active
        and tool_name == "todo"
        and not checklist_seeded
        and goal_created_at is not None
    ):
        _mark_checklist_seeded(session_id, goal_created_at)

    if directive is not None:
        logger.info("phoenix_v7 guardrails: tool=%s directive=%s", tool_name, directive["action"])
    return directive


def _on_subagent_stop(**context) -> None:
    parent_session_id = context.get("parent_session_id") or ""
    child_summary = (context.get("child_summary") or "").strip()
    if not parent_session_id or not child_summary:
        return
    if child_summary.upper().startswith("APPROVED"):
        _pending_loop_approvals[parent_session_id] = True
        logger.info(
            "phoenix_v7 loop: evaluator approved pending high-tier action for session=%s",
            parent_session_id,
        )


def _check_hallucination(**context) -> str | None:
    response_text = context.get("response_text") or ""
    if not response_text:
        return None
    session_id = context.get("session_id", "")
    tier = _last_tier_by_session.get(session_id)
    result = _evaluate_hallucination(
        response_text, tier, lambda: get_text_auxiliary_client(task="hallucination_check")
    )
    if result is not None:
        logger.info("phoenix_v7 verify: hallucination check flagged a response, tier=%s", tier)
    return result


def _resolved_model_for(context: dict) -> str | None:
    """优先用 _route() 记录的"这个session真正调用的模型"，兜底才用
    context.get("model")（= agent.model，_route() 从没被调用过这个session时的
    唯一信息来源，比如路由钩子因为某种原因没跑到）。"""
    session_id = context.get("session_id", "")
    if session_id and session_id in _resolved_model_by_session:
        return _resolved_model_by_session[session_id]
    return context.get("model")


def _record_usage(**context) -> None:
    usage = context.get("usage") or {}
    total_tokens = usage.get("total_tokens", 0) or 0
    usd = (total_tokens / 1000.0) * _USD_PER_1K_TOKENS
    _cost_monitor.record(usd)
    _breaker.record_success()
    model = _resolved_model_for(context)
    if model:
        _model_health.record_success(model)


def _record_api_error(**context) -> None:
    _breaker.record_failure()
    model = _resolved_model_for(context)
    error_type = (context.get("error") or {}).get("type")
    if model and error_type:
        _model_health.record_failure(model, error_type)


def _heal(tool_name: str, args: dict, next_call, **context):
    """tool_execution middleware：工具调用失败时查 antibody 表，命中就把处理建议
    附加进异常消息里带回给模型（下一轮它能看到"提示"自己决定要不要重试），未命中
    3次后升级提醒。

    没有按 Task 11 brief 原稿那样在这里对 next_call() 调用两次做"重试"：Hermes
    real middleware 契约（hermes_cli/middleware.py::_run_execution_chain，docs/
    middleware/README.md "Execution middleware should call next_call(...) exactly
    once"）明确 next_call 单次消费，第二次调用会直接抛 RuntimeError（"next_call()
    more than once"），不会真的重跑下游工具。改为查表 + 把 fix_hint 拼进异常消息
    向上抛，真正的重试落在模型看到提示后自己再发起一次工具调用（会重新进入这个
    middleware）。"""
    session_id = context.get("session_id", "")
    try:
        result = next_call(args)
    except Exception as exc:
        error_message = str(exc)
        outcome = _error_processor.handle(tool_name=tool_name, error_message=error_message)
        if outcome.fix_hint:
            logger.info("phoenix_v7 selfheal: %s -> retrying with hint: %s", tool_name, outcome.fix_hint)
            matched_pattern = _antibody.match_pattern(error_message)
            if matched_pattern is not None:
                _antibody.record_outcome(matched_pattern, success=False)
                _error_processor.record_pending_fix(session_id, tool_name, matched_pattern)
            raise RuntimeError(f"{exc}\n[phoenix_v7 selfheal 建议] {outcome.fix_hint}") from exc
        if outcome.escalate:
            _antibody.record(error_message[:200], "未知错误，人工介入后请补充处理方式")
            logger.warning("phoenix_v7 selfheal: %s failed 3x, escalating to user: %s", tool_name, exc)
        raise
    else:
        pattern = _error_processor.pop_pending_fix(session_id, tool_name)
        if pattern is not None:
            _antibody.record_outcome(pattern, success=True)
            logger.info("phoenix_v7 selfheal: %s succeeded after hint, resetting failure streak for %r", tool_name, pattern)
        return result


def _setup_router_cli(subparser) -> None:
    subparser.add_argument("state", choices=["on", "off"], help="on=自动切换模型, off=只判断不切换")


def _handle_router_cli(args) -> None:
    enabled = args.state == "on"
    write_enabled(enabled)
    status = "已开启（会按档位自动切换模型）" if enabled else "已关闭（只判断档位，不切换模型）"
    print(f"phoenix_v7 自动路由: {status}")


def _setup_status_cli(subparser) -> None:
    pass


def _handle_status_cli(args) -> None:
    enabled, _overrides = load_tier_overrides()
    router_status = "自动挡" if enabled else "手动挡"
    breaker_state = _breaker.state()
    daily_cost = _cost_monitor.daily_total()
    antibody_stats = _antibody.stats()

    running_version = _read_hermes_version()
    verified_version = _read_verified_hermes_version()
    if verified_version is None:
        compat = "unknown"
    else:
        compat = check_hermes_compatibility(verified_version)
    if compat == "match":
        hermes_version_line = f"Hermes 版本: v{running_version}（已验证）"
    elif compat == "newer":
        hermes_version_line = (
            f"Hermes 版本: v{running_version}"
            f"（比不死鸟验证过的 v{verified_version} 新，建议核实一遍兼容性）"
        )
    elif compat == "older":
        hermes_version_line = (
            f"Hermes 版本: v{running_version}"
            f"（比不死鸟验证过的 v{verified_version} 旧，未测试过，可能有问题）"
        )
    else:
        hermes_version_line = "Hermes 版本: 无法读取（不影响不死鸟其它功能）"

    print(
        "phoenix_v7 状态\n"
        f"  路由: {router_status}\n"
        f"  熔断器: {breaker_state}\n"
        "  长任务(Loop): 用 Hermes 原生 `/goal status` 查看（不死鸟在此基础上加了"
        "清单强制+高危操作复核，见 docs/Loop长任务使用指南.md）\n"
        f"  {hermes_version_line}\n"
        f"  今日花费(估算，非真实计费): ${daily_cost:.4f}\n"
        f"  抗体库: {antibody_stats['total_patterns']} 个已知模式"
        f"（{antibody_stats['disabled_patterns']} 个已停用）"
    )


def register(ctx) -> None:
    logger.info("phoenix_v7: plugin registered")
    ctx.register_middleware("llm_request", _route)
    ctx.register_hook("pre_tool_call", _guard_tool)
    ctx.register_hook("post_api_request", _record_usage)
    ctx.register_hook("api_request_error", _record_api_error)
    ctx.register_hook("subagent_stop", _on_subagent_stop)
    ctx.register_hook("transform_llm_output", _check_hallucination)
    ctx.register_middleware("tool_execution", _heal)
    ctx.register_cli_command(
        "phoenix-router",
        help="开关不死鸟自动路由换模型",
        setup_fn=_setup_router_cli,
        handler_fn=_handle_router_cli,
        description="hermes phoenix-router on|off",
    )
    ctx.register_cli_command(
        "phoenix-status",
        help="查看不死鸟当前状态",
        setup_fn=_setup_status_cli,
        handler_fn=_handle_status_cli,
        description="hermes phoenix-status",
    )
