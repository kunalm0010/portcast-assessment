import time

from rate_limiter.circuit import CircuitBreaker, CircuitState


def test_circuit_opens_after_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=3, failure_window_sec=10.0, open_duration_sec=30.0)
    assert breaker.allow_request() is True
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request() is False


def test_circuit_half_open_then_closes_on_success() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2,
        open_duration_sec=0.1,
        success_threshold=2,
    )
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    time.sleep(0.15)
    assert breaker.allow_request() is True
    breaker.record_success()
    assert breaker.allow_request() is True
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
