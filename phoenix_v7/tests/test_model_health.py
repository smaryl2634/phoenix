import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.model_health import ModelHealthTracker


def test_unknown_model_is_available_by_default():
    tracker = ModelHealthTracker()
    assert tracker.is_available("some-model") is True


def test_record_success_keeps_model_available():
    tracker = ModelHealthTracker()
    tracker.record_success("model-a")
    assert tracker.is_available("model-a") is True


def test_record_failure_below_threshold_stays_available():
    tracker = ModelHealthTracker(failure_threshold=2, cooldown_seconds=60)
    tracker.record_failure("model-a", "TimeoutError")
    assert tracker.is_available("model-a") is True


def test_record_failure_reaching_threshold_triggers_cooldown():
    now = [1000.0]
    tracker = ModelHealthTracker(failure_threshold=2, cooldown_seconds=60, now_func=lambda: now[0])
    tracker.record_failure("model-a", "TimeoutError")
    tracker.record_failure("model-a", "TimeoutError")
    assert tracker.is_available("model-a") is False


def test_cooldown_expires_after_cooldown_seconds():
    now = [1000.0]
    tracker = ModelHealthTracker(failure_threshold=1, cooldown_seconds=60, now_func=lambda: now[0])
    tracker.record_failure("model-a", "TimeoutError")
    assert tracker.is_available("model-a") is False
    now[0] = 1061.0  # 61 秒后，超过冷却期
    assert tracker.is_available("model-a") is True


def test_non_health_error_type_does_not_trigger_cooldown():
    # 比如权限错误/参数错误这类不是"这个模型暂时不可用"，不该被计入健康失败
    tracker = ModelHealthTracker(failure_threshold=1)
    tracker.record_failure("model-a", "AuthenticationError")
    assert tracker.is_available("model-a") is True


def test_success_resets_failure_state():
    now = [1000.0]
    tracker = ModelHealthTracker(failure_threshold=1, cooldown_seconds=60, now_func=lambda: now[0])
    tracker.record_failure("model-a", "TimeoutError")
    assert tracker.is_available("model-a") is False
    tracker.record_success("model-a")
    assert tracker.is_available("model-a") is True


def test_ordered_candidates_puts_healthy_models_first():
    now = [1000.0]
    tracker = ModelHealthTracker(failure_threshold=1, cooldown_seconds=60, now_func=lambda: now[0])
    tracker.record_failure("model-bad", "TimeoutError")
    result = tracker.ordered_candidates(["model-bad", "model-good"])
    assert result == ["model-good", "model-bad"]


def test_ordered_candidates_all_healthy_preserves_order():
    tracker = ModelHealthTracker()
    result = tracker.ordered_candidates(["model-a", "model-b", "model-c"])
    assert result == ["model-a", "model-b", "model-c"]
