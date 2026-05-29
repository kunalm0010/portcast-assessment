"""Load tier, route, and client limit configuration from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rate_limiter.models import LimitPolicy


class RateLimitConfig:
    def __init__(
        self,
        tiers: dict[str, dict[str, LimitPolicy]],
        routes: dict[str, dict[str, LimitPolicy]],
        clients: dict[str, str],
        client_overrides: dict[str, dict[str, LimitPolicy]],
    ) -> None:
        self._tiers = tiers
        self._routes = routes
        self._clients = clients
        self._client_overrides = client_overrides

    @classmethod
    def load(cls, limits_path: Path, clients_path: Path) -> RateLimitConfig:
        limits_raw = yaml.safe_load(limits_path.read_text()) or {}
        clients_raw = yaml.safe_load(clients_path.read_text()) or {}

        tiers = _parse_tier_section(limits_raw.get("tiers", {}))
        routes = _parse_route_section(limits_raw.get("routes", {}))
        clients = dict(clients_raw.get("clients", {}))
        client_overrides = _parse_client_overrides(clients_raw.get("overrides", {}))
        return cls(tiers, routes, clients, client_overrides)

    def resolve_policy(self, client_id: str, route: str) -> "LimitPolicy | None":
        tier = self._clients.get(client_id)
        if tier is None:
            return None

        override_routes = self._client_overrides.get(client_id, {})
        if route in override_routes:
            return override_routes[route]

        route_tiers = self._routes.get(route, {})
        if tier in route_tiers:
            return route_tiers[tier]

        tier_defaults = self._tiers.get(tier, {})
        return tier_defaults.get("default")

    def known_client_ids(self) -> set[str]:
        return set(self._clients.keys())


def _parse_limit_block(raw: dict[str, Any]) -> LimitPolicy:
    return LimitPolicy(
        rate_per_sec=float(raw["rate_per_sec"]),
        burst=float(raw["burst"]),
    )


def _parse_tier_section(raw: dict[str, Any]) -> dict[str, dict[str, LimitPolicy]]:
    result: dict[str, dict[str, LimitPolicy]] = {}
    for tier_name, tier_body in raw.items():
        parsed: dict[str, LimitPolicy] = {}
        for key, value in tier_body.items():
            parsed[key] = _parse_limit_block(value)
        result[tier_name] = parsed
    return result


def _parse_route_section(raw: dict[str, Any]) -> dict[str, dict[str, LimitPolicy]]:
    result: dict[str, dict[str, LimitPolicy]] = {}
    for route, tier_map in raw.items():
        result[route] = {tier: _parse_limit_block(cfg) for tier, cfg in tier_map.items()}
    return result


def _parse_client_overrides(raw: dict[str, Any]) -> dict[str, dict[str, LimitPolicy]]:
    result: dict[str, dict[str, LimitPolicy]] = {}
    for client_id, routes in raw.items():
        result[client_id] = {
            route: _parse_limit_block(cfg) for route, cfg in routes.items()
        }
    return result
