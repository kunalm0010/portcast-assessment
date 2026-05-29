"""Unit tests that do not require Redis."""

from rate_limiter.limiter import build_redis_key


def test_redis_key_format() -> None:
    assert build_redis_key("client-a", "GET /v1/demo") == "rl:client-a:GET /v1/demo"
