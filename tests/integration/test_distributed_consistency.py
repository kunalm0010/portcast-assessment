"""Two limiter instances (two API processes) share one Redis primary."""

import pytest

from rate_limiter.circuit import CircuitBreaker
from rate_limiter.limiter import RateLimiter
from rate_limiter.models import LimiterOutcome
from rate_limiter.redis_store import RedisRateLimitStore

pytestmark = pytest.mark.integration


def test_two_instances_share_one_quota(rate_limit_config, redis_url, require_redis) -> None:
    store_a = RedisRateLimitStore(redis_url=redis_url, socket_timeout_sec=0.1)
    store_b = RedisRateLimitStore(redis_url=redis_url, socket_timeout_sec=0.1)
    limiter_a = RateLimiter(rate_limit_config, store_a, CircuitBreaker())
    limiter_b = RateLimiter(rate_limit_config, store_b, CircuitBreaker())

    client_id = "client-free-1"
    route = "GET /v1/demo"
    outcomes = []

    for _ in range(3):
        outcomes.append(limiter_a.allow(client_id, route).outcome)
        outcomes.append(limiter_b.allow(client_id, route).outcome)

    assert outcomes.count(LimiterOutcome.ALLOWED) == 6
    next_a = limiter_a.allow(client_id, route)
    next_b = limiter_b.allow(client_id, route)
    assert next_a.outcome == LimiterOutcome.RATE_LIMITED
    assert next_b.outcome == LimiterOutcome.RATE_LIMITED

    store_a.close()
    store_b.close()
