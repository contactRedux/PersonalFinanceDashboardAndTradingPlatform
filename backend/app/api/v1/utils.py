"""
Utility endpoints for the v1 API.

  GET /api/v1/limits — returns the current rate-limit configuration.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/limits")
async def get_rate_limits() -> dict:
    """
    Return the active rate-limit tiers so clients can self-throttle.

    Tiers (applied per IP, sliding 60-second window):
      - auth_endpoints : /api/v1/auth/*  — 10 req/min  (brute-force protection)
      - api_endpoints  : all other /api/* — 200 req/min
      - websocket      : /ws/*            — unlimited (long-lived connections)
    """
    return {
        "auth_endpoints": "10 req/min",
        "api_endpoints": "200 req/min",
        "websocket": "unlimited",
    }
