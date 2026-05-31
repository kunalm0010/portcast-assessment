from pathlib import Path

from rate_limiter.config import RateLimitConfig

ROOT = Path(__file__).resolve().parent.parent.parent


def test_resolve_tier_default() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    policy = config.resolve_policy("client-free-1", "GET /v1/unknown-route")
    assert policy is not None
    assert policy.rate_per_sec == 10
    assert policy.burst == 20


def test_resolve_route_override() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    policy = config.resolve_policy("client-free-1", "GET /v1/search")
    assert policy is not None
    assert policy.rate_per_sec == 5
    assert policy.burst == 10


def test_resolve_client_override() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    policy = config.resolve_policy("client-enterprise-1", "GET /v1/shipments")
    assert policy is not None
    assert policy.rate_per_sec == 150
    assert policy.burst == 300


def test_enterprise_without_override_uses_tier_default() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    policy = config.resolve_policy("client-enterprise-2", "GET /v1/shipments")
    assert policy is not None
    assert policy.rate_per_sec == 100
    assert policy.burst == 200


def test_enterprise_without_override_uses_route_override_when_defined() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    policy = config.resolve_policy("client-enterprise-2", "GET /v1/search")
    assert policy is not None
    assert policy.rate_per_sec == 80
    assert policy.burst == 160


def test_enterprise_clients_resolve_different_policies_on_overridden_route() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    with_override = config.resolve_policy("client-enterprise-1", "GET /v1/shipments")
    without_override = config.resolve_policy("client-enterprise-2", "GET /v1/shipments")
    assert with_override is not None
    assert without_override is not None
    assert with_override.rate_per_sec == 150
    assert without_override.rate_per_sec == 100


def test_known_clients_includes_enterprise_without_override() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    assert "client-enterprise-2" in config.known_client_ids()


def test_unknown_client_returns_none() -> None:
    config = RateLimitConfig.load(
        ROOT / "configs" / "limits.yaml",
        ROOT / "configs" / "clients.yaml",
    )
    assert config.resolve_policy("not-registered", "GET /v1/demo") is None
