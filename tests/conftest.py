from __future__ import annotations

import os
from pathlib import Path

import pytest
import redis as redis_lib

from rate_limiter.circuit import CircuitBreaker
from rate_limiter.config import RateLimitConfig
from rate_limiter.limiter import RateLimiter
from rate_limiter.redis_store import RedisRateLimitStore

ROOT = Path(__file__).resolve().parent.parent
LIMITS_PATH = ROOT / "configs" / "limits.yaml"
CLIENTS_PATH = ROOT / "configs" / "clients.yaml"


@pytest.fixture(scope="session")
def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(scope="session")
def redis_available(redis_url: str) -> bool:
    try:
        client = redis_lib.from_url(redis_url)
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def require_redis(redis_available: bool) -> None:
    if not redis_available:
        pytest.skip("Redis is not available")


@pytest.fixture
def redis_client(redis_url: str, require_redis: None) -> redis_lib.Redis:
    client = redis_lib.from_url(redis_url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture
def rate_limit_config() -> RateLimitConfig:
    return RateLimitConfig.load(LIMITS_PATH, CLIENTS_PATH)


@pytest.fixture
def redis_store(redis_url: str, require_redis: None, redis_client) -> RedisRateLimitStore:
    """Redis store fixture that flushes before and after each test."""
    timeout_ms = float(os.getenv("REDIS_TIMEOUT_MS", "100"))
    store = RedisRateLimitStore(
        redis_url=redis_url,
        socket_timeout_sec=timeout_ms / 1000.0,
    )
    # Flush before test starts
    redis_client.flushdb()
    yield store
    # Flush after test ends
    redis_client.flushdb()
    store.close()


@pytest.fixture
def rate_limiter(
    rate_limit_config: RateLimitConfig,
    redis_store: RedisRateLimitStore,
) -> RateLimiter:
    return RateLimiter(
        config=rate_limit_config,
        store=redis_store,
        circuit_breaker=CircuitBreaker(
            failure_threshold=3,
            failure_window_sec=5.0,
            open_duration_sec=2.0,
            success_threshold=2,
        ),
    )
