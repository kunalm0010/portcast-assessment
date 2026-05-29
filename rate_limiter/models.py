from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LimiterOutcome(Enum):
    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_CLIENT = "invalid_client"


@dataclass(frozen=True)
class LimitPolicy:
    rate_per_sec: float
    burst: float


@dataclass(frozen=True)
class AllowResult:
    outcome: LimiterOutcome
    allowed: bool
    remaining: int = 0
    reset_at: int = 0
    retry_after: int | None = None

    @property
    def service_unavailable(self) -> bool:
        return self.outcome == LimiterOutcome.SERVICE_UNAVAILABLE
