"""
middleware/rate_limit.py — Redis-backed per-IP rate limiting middleware.

Strategy:
  - Sliding window counter using Redis INCR + EXPIRE.
  - Configurable burst window (default 60 s) and max requests per window.
  - /api/v1/auth/* endpoints use a tighter limit (10 req/60s).
  - All other /api/* endpoints use 120 req/60s.
  - Exempt: /health, /api/docs, /api/openapi.json

Returns HTTP 429 with Retry-After header when limit is exceeded.
"""

from __future__ import annotations

import time

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# ─── Rate limit tiers (requests per window_seconds) ──────────────────────────
_AUTH_LIMIT = 10  # tight limit for auth endpoints
_API_LIMIT = 120  # general API limit
_WINDOW_SEC = 60  # sliding window size

_EXEMPT_PATHS = {"/health", "/api/docs", "/api/redoc", "/api/openapi.json"}
_AUTH_PREFIX = "/api/v1/auth"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed sliding window rate limiter.

    Key schema:
        rl:{client_ip}:{tier}:{window_bucket}
        → integer counter, expires after WINDOW_SEC seconds.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        path = request.url.path

        # Exempt health / docs / static
        if path in _EXEMPT_PATHS or path.startswith("/_next/"):
            return await call_next(request)  # type: ignore[operator]

        # Determine tier
        is_auth = path.startswith(_AUTH_PREFIX)
        limit = _AUTH_LIMIT if is_auth else _API_LIMIT
        tier = "auth" if is_auth else "api"

        # Extract client IP (honour X-Forwarded-For from NGINX)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )

        # Build Redis key for current window bucket
        bucket = int(time.time()) // _WINDOW_SEC
        redis_key = f"rl:{client_ip}:{tier}:{bucket}"

        try:
            from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415

            redis = await get_redis_pool()
            count: int = await redis.incr(redis_key)
            if count == 1:
                # First request in this window: set TTL
                await redis.expire(redis_key, _WINDOW_SEC * 2)

            if count > limit:
                retry_after = _WINDOW_SEC - (int(time.time()) % _WINDOW_SEC)
                logger.warning(
                    "rate_limit.exceeded",
                    ip=client_ip,
                    path=path,
                    tier=tier,
                    count=count,
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception as exc:  # noqa: BLE001
            # If Redis is unavailable, fail open — never block legitimate traffic.
            logger.warning("rate_limit.redis_error", error=str(exc))

        return await call_next(request)  # type: ignore[operator]
