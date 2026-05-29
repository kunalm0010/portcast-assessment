"""Redis connection pool and token-bucket Lua execution."""

from __future__ import annotations

import time
from pathlib import Path

import redis
from redis.exceptions import RedisError

_LUA_PATH = Path(__file__).parent / "lua" / "token_bucket.lua"
_TOKEN_BUCKET_SCRIPT = _LUA_PATH.read_text()


class RedisRateLimitStore:
    def __init__(
        self,
        redis_url: str,
        socket_timeout_sec: float = 0.005,
        max_connections: int = 50,
    ) -> None:
        self._client = redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=socket_timeout_sec,
            socket_timeout=socket_timeout_sec,
            max_connections=max_connections,
        )
        self._script = self._client.register_script(_TOKEN_BUCKET_SCRIPT)

    def consume(
        self,
        key: str,
        rate_per_sec: float,
        burst: float,
    ) -> tuple[bool, int, int, int]:
        now = time.time()
        raw = self._script(
            keys=[key],
            args=[rate_per_sec, burst, now],
        )
        allowed = int(raw[0]) == 1
        remaining = int(raw[1])
        reset_at = int(raw[2])
        retry_after = int(raw[3])
        return allowed, remaining, reset_at, retry_after

    def ping(self) -> bool:
        return bool(self._client.ping())

    def close(self) -> None:
        self._client.close()


class RedisUnavailable(Exception):
    """Raised when Redis cannot complete a rate-limit check."""


def consume_or_raise(
    store: RedisRateLimitStore,
    key: str,
    rate_per_sec: float,
    burst: float,
) -> tuple[bool, int, int, int]:
    try:
        return store.consume(key, rate_per_sec, burst)
    except (RedisError, OSError) as exc:
        raise RedisUnavailable(str(exc)) from exc
