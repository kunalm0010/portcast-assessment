import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware

pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(rate_limiter) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/demo")
    def demo() -> dict[str, str]:
        return {"ok": "true"}

    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)
    return TestClient(app)


def test_missing_client_id_returns_400(api_client: TestClient) -> None:
    response = api_client.get("/v1/demo")
    assert response.status_code == 400


def test_rate_limit_returns_429(api_client: TestClient) -> None:
    headers = {"X-Client-Id": "client-free-1"}
    for _ in range(6):
        assert api_client.get("/v1/demo", headers=headers).status_code == 200
    blocked = api_client.get("/v1/demo", headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "X-RateLimit-Remaining" in blocked.headers


def test_health_bypasses_limiter(api_client: TestClient) -> None:
    assert api_client.get("/health").status_code == 200
