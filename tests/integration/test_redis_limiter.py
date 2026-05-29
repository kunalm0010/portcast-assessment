import pytest

from rate_limiter.models import LimiterOutcome

pytestmark = pytest.mark.integration


def test_token_bucket_allows_up_to_burst(rate_limiter) -> None:
    client_id = "client-free-1"
    route = "GET /v1/demo"
    # free tier on this route: rate 3, burst 6
    allowed_count = 0
    for _ in range(6):
        result = rate_limiter.allow(client_id, route)
        assert result.outcome == LimiterOutcome.ALLOWED
        allowed_count += 1
    assert allowed_count == 6

    denied = rate_limiter.allow(client_id, route)
    assert denied.outcome == LimiterOutcome.RATE_LIMITED
    assert denied.retry_after is not None


def test_different_clients_have_separate_buckets(rate_limiter) -> None:
    route = "GET /v1/demo"
    for _ in range(6):
        assert rate_limiter.allow("client-free-1", route).allowed is True
    assert rate_limiter.allow("client-free-1", route).allowed is False
    assert rate_limiter.allow("client-standard-1", route).allowed is True
