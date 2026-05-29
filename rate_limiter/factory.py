"""Build RateLimiter from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from rate_limiter.circuit import CircuitBreaker
from rate_limiter.config import RateLimitConfig
from rate_limiter.limiter import RateLimiter
from rate_limiter.redis_store import RedisRateLimitStore

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


def create_rate_limiter() -> RateLimiter:
    config_dir = Path(os.getenv("CONFIG_DIR", str(_DEFAULT_CONFIG_DIR)))
    limits_path = Path(os.getenv("LIMITS_PATH", config_dir / "limits.yaml"))
    clients_path = Path(os.getenv("CLIENTS_PATH", config_dir / "clients.yaml"))

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    timeout_ms = float(os.getenv("REDIS_TIMEOUT_MS", "5"))
    timeout_sec = max(timeout_ms, 1.0) / 1000.0

    config = RateLimitConfig.load(limits_path, clients_path)
    store = RedisRateLimitStore(redis_url=redis_url, socket_timeout_sec=timeout_sec)
    breaker = CircuitBreaker(
        failure_threshold=int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5")),
        failure_window_sec=float(os.getenv("CIRCUIT_FAILURE_WINDOW_SEC", "10")),
        open_duration_sec=float(os.getenv("CIRCUIT_OPEN_DURATION_SEC", "30")),
        success_threshold=int(os.getenv("CIRCUIT_SUCCESS_THRESHOLD", "3")),
    )
    return RateLimiter(config=config, store=store, circuit_breaker=breaker)
