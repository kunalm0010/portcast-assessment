"""Tests for circuit breaker failover functionality."""

from rate_limiter.circuit import CircuitBreaker, CircuitState


def test_circuit_reset_on_failover_from_open():
    """Test that reset_on_failover transitions OPEN to HALF_OPEN."""
    breaker = CircuitBreaker(failure_threshold=2, open_duration_sec=60.0)
    
    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    
    # Reset on failover should transition to HALF_OPEN immediately
    breaker.reset_on_failover()
    assert breaker.state == CircuitState.HALF_OPEN


def test_circuit_reset_on_failover_clears_failures():
    """Test that reset_on_failover clears failure history."""
    breaker = CircuitBreaker(failure_threshold=2)
    
    breaker.record_failure()
    breaker.record_failure()
    
    assert len(breaker._failures) > 0
    breaker.reset_on_failover()
    assert len(breaker._failures) == 0


def test_circuit_reset_on_failover_resets_streak():
    """Test that reset_on_failover resets success streak."""
    breaker = CircuitBreaker(
        failure_threshold=2,
        open_duration_sec=0.1,
        success_threshold=2,
    )
    
    # Open circuit
    breaker.record_failure()
    breaker.record_failure()
    
    # Transition to HALF_OPEN normally
    import time
    time.sleep(0.15)
    breaker.allow_request()
    breaker.record_success()
    assert breaker._success_streak == 1
    
    # Reset should clear streak
    breaker.reset_on_failover()
    assert breaker._success_streak == 0
    assert breaker.state == CircuitState.HALF_OPEN


def test_circuit_reset_on_failover_clears_opened_at():
    """Test that reset_on_failover clears opened_at timestamp."""
    breaker = CircuitBreaker(failure_threshold=2)
    
    breaker.record_failure()
    breaker.record_failure()
    assert breaker._opened_at is not None
    
    breaker.reset_on_failover()
    assert breaker._opened_at is None


def test_circuit_reset_on_failover_allows_immediate_probe():
    """Test that after reset_on_failover, next request is allowed as probe."""
    breaker = CircuitBreaker(failure_threshold=2)
    
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.allow_request() is False  # Circuit is OPEN
    
    breaker.reset_on_failover()
    assert breaker.state == CircuitState.HALF_OPEN
    assert breaker.allow_request() is True  # Should allow probe request
