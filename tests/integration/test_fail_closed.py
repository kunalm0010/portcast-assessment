import pytest

from rate_limiter.circuit import CircuitBreaker
from rate_limiter.config import RateLimitConfig
from rate_limiter.limiter import RateLimiter
from rate_limiter.models import LimiterOutcome
from rate_limiter.redis_store import RedisRateLimitStore

pytestmark = pytest.mark.integration


def test_fail_closed_when_redis_unreachable(rate_limit_config) -> None:
    store = RedisRateLimitStore(
        redis_url="redis://127.0.0.1:1/0",
        socket_timeout_sec=0.05,
    )
    limiter = RateLimiter(
        config=rate_limit_config,
        store=store,
        circuit_breaker=CircuitBreaker(failure_threshold=2, open_duration_sec=5.0),
    )
    result = limiter.allow("client-free-1", "GET /v1/demo")
    assert result.outcome == LimiterOutcome.SERVICE_UNAVAILABLE
    assert result.allowed is False
    store.close()


def test_circuit_opens_and_skips_redis(rate_limit_config) -> None:
    store = RedisRateLimitStore(
        redis_url="redis://127.0.0.1:1/0",
        socket_timeout_sec=0.05,
    )
    breaker = CircuitBreaker(failure_threshold=2, open_duration_sec=60.0)
    limiter = RateLimiter(config=rate_limit_config, store=store, circuit_breaker=breaker)

    limiter.allow("client-free-1", "GET /v1/demo")
    limiter.allow("client-free-1", "GET /v1/demo")
    third = limiter.allow("client-free-1", "GET /v1/demo")
    assert third.outcome == LimiterOutcome.SERVICE_UNAVAILABLE
    store.close()
