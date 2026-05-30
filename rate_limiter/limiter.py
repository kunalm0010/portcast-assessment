"""Rate limiter orchestration: config, Redis, circuit breaker."""

from __future__ import annotations

from rate_limiter.circuit import CircuitBreaker
from rate_limiter.config import RateLimitConfig
from rate_limiter.models import AllowResult, LimiterOutcome
from rate_limiter.redis_store import RedisRateLimitStore, RedisUnavailable, consume_or_raise


def build_redis_key(client_id: str, route: str) -> str:
    return f"rl:{client_id}:{route}"


class RateLimiter:
    def __init__(
        self,
        config: RateLimitConfig,
        store: RedisRateLimitStore,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._circuit = circuit_breaker or CircuitBreaker()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit

    def set_config(self, config: RateLimitConfig) -> None:
        """Update config (used by config reloader)."""
        self._config = config

    def allow(self, client_id: str, route: str) -> AllowResult:
        if not client_id or not client_id.strip():
            return AllowResult(
                outcome=LimiterOutcome.INVALID_CLIENT,
                allowed=False,
            )

        policy = self._config.resolve_policy(client_id, route)
        if policy is None:
            return AllowResult(
                outcome=LimiterOutcome.INVALID_CLIENT,
                allowed=False,
            )

        if not self._circuit.allow_request():
            return AllowResult(
                outcome=LimiterOutcome.SERVICE_UNAVAILABLE,
                allowed=False,
                retry_after=30,
            )

        key = build_redis_key(client_id, route)
        try:
            allowed, remaining, reset_at, retry_after = consume_or_raise(
                self._store,
                key,
                policy.rate_per_sec,
                policy.burst,
            )
        except RedisUnavailable:
            self._circuit.record_failure()
            return AllowResult(
                outcome=LimiterOutcome.SERVICE_UNAVAILABLE,
                allowed=False,
                retry_after=30,
            )

        self._circuit.record_success()
        if allowed:
            return AllowResult(
                outcome=LimiterOutcome.ALLOWED,
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
            )
        return AllowResult(
            outcome=LimiterOutcome.RATE_LIMITED,
            allowed=False,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after if retry_after > 0 else 1,
        )
