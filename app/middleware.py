"""HTTP middleware: enforce distributed rate limits before route handlers."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from rate_limiter.limiter import RateLimiter
from rate_limiter.models import LimiterOutcome

_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def route_key(request: Request) -> str:
    return f"{request.method} {request.url.path}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_id = request.headers.get("X-Client-Id", "").strip()
        route = route_key(request)
        result = self._limiter.allow(client_id, route)

        if result.outcome == LimiterOutcome.INVALID_CLIENT:
            return JSONResponse(
                status_code=400,
                content={"detail": "Missing or unknown X-Client-Id"},
            )

        if result.outcome == LimiterOutcome.SERVICE_UNAVAILABLE:
            headers = {}
            if result.retry_after is not None:
                headers["Retry-After"] = str(result.retry_after)
            return JSONResponse(
                status_code=503,
                content={"detail": "Service unavailable"},
                headers=headers,
            )

        if result.outcome == LimiterOutcome.RATE_LIMITED:
            headers = {
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_at),
            }
            if result.retry_after is not None:
                headers["Retry-After"] = str(result.retry_after)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry later"},
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        return response
