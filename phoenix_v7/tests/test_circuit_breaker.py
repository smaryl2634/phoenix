import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guardrails.circuit_breaker import CircuitBreaker


def test_closed_by_default_allows_calls():
    cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=60)
    assert cb.allow() is True


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=60)
    for _ in range(3):
        cb.record_failure()
    assert cb.allow() is False


def test_success_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3, reset_after_seconds=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert cb.allow() is True  # 只有1次连续失败，没到阈值3


def test_state_closed_by_default():
    breaker = CircuitBreaker(failure_threshold=3, reset_after_seconds=300)
    assert breaker.state() == "closed"


def test_state_open_after_threshold_failures():
    breaker = CircuitBreaker(failure_threshold=2, reset_after_seconds=300)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state() == "open"


def test_state_half_open_after_reset_window():
    breaker = CircuitBreaker(failure_threshold=1, reset_after_seconds=0)
    breaker.record_failure()
    # reset_after_seconds=0 意味着任何经过的时间都满足重置窗口
    assert breaker.state() == "half_open"
