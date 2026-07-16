"""
FactSet Open API adapter — institutional fundamentals from the FactSet developer tier.

Free tier limits: ~250 requests / day.
All responses are Redis-cached (TTL 4 h) to stay within the daily quota.

FactSet API authentication: HTTP Basic Auth where the username is your FactSet
username and the password is your FactSet API key. Store as a single value in
the format "username:apikey" in FACTSET_API_KEY.

Endpoints used:
  GET /company/v1/profile/{id}               — company profile + sector
  GET /fundamentals/v2/financials/{id}       — income statement (annual)
  GET /fundamentals/v2/financials/{id}       — balance sheet (annual)
  GET /fundamentals/v2/financials/{id}       — cash flow (annual)
  GET /estimates/rolling/v3/consensus        — consensus EPS/revenue estimates

Free developer access: https://developer.factset.com
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_FACTSET_BASE = "https://api.factset.com"
_CACHE_TTL = 60 * 60 * 4  # 4 hours


# ─── Redis cache helpers ──────────────────────────────────────────────────────

async def _cache_get(key: str) -> str | None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        return await redis.get(key)
    except Exception:  # noqa: BLE001
        return None


async def _cache_set(key: str, value: str, ttl: int = _CACHE_TTL) -> None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        await redis.setex(key, ttl, value)
    except Exception:  # noqa: BLE001
        pass


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _factset_auth() -> tuple[str, str] | None:
    """
    Parse FACTSET_API_KEY as "username:apikey" and return (username, apikey).
    Returns None if the key is not configured or malformed.
    """
    raw = settings.factset_api_key
    if not raw or ":" not in raw:
        return None
    username, _, apikey = raw.partition(":")
    return (username.strip(), apikey.strip()) if username and apikey else None


# ─── Adapter ──────────────────────────────────────────────────────────────────

class FactSetAdapter:
    """
    FactSet Open API adapter for institutional-grade fundamentals data.

    Requires FACTSET_API_KEY to be set in the format "username:apikey".
    Returns empty dicts / empty lists gracefully when not configured.
    """

    def _is_available(self) -> bool:
        return _factset_auth() is not None

    async def get_profile(self, symbol: str) -> dict:
        """Return company profile from FactSet (sector, description, identifiers)."""
        if not self._is_available():
            return {}

        sym = symbol.upper()
        cache_key = f"factset:profile:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        auth = _factset_auth()
        url = f"{_FACTSET_BASE}/company/v1/profile/{sym}-US"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, auth=auth)  # type: ignore[arg-type]
                if resp.status_code == 404:
                    return {}
                resp.raise_for_status()
                data = resp.json()

            profile = data.get("data", {})
            result = {
                "symbol": sym,
                "name": profile.get("name", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "description": profile.get("description", ""),
                "exchange": profile.get("exchange", ""),
                "country": profile.get("country", ""),
                "factset_id": profile.get("factsetId", ""),
                "source": "factset",
            }
            await _cache_set(cache_key, json.dumps(result))
            return result
        except Exception:
            logger.exception("factset.get_profile.error", symbol=sym)
            return {}

    async def get_financials(self, symbol: str) -> dict:
        """
        Return annual income statement, balance sheet, and cash flow data.
        Returns {"income": [...], "balance": [...], "cashflow": [...]}
        """
        if not self._is_available():
            return {}

        sym = symbol.upper()
        cache_key = f"factset:financials:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        auth = _factset_auth()
        url = f"{_FACTSET_BASE}/fundamentals/v2/financials/{sym}-US"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    url,
                    params={"periodicity": "ANNUAL", "limit": 5},
                    auth=auth,  # type: ignore[arg-type]
                )
                if resp.status_code == 404:
                    return {}
                resp.raise_for_status()
                data = resp.json()

            result = {
                "symbol": sym,
                "income": data.get("data", {}).get("incomeStatement", []),
                "balance": data.get("data", {}).get("balanceSheet", []),
                "cashflow": data.get("data", {}).get("cashFlowStatement", []),
                "source": "factset",
                "as_of": datetime.now(UTC).isoformat(),
            }
            await _cache_set(cache_key, json.dumps(result))
            return result
        except Exception:
            logger.exception("factset.get_financials.error", symbol=sym)
            return {}

    async def get_estimates(self, symbol: str) -> dict:
        """
        Return consensus EPS and revenue estimates (rolling consensus).
        """
        if not self._is_available():
            return {}

        sym = symbol.upper()
        cache_key = f"factset:estimates:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        auth = _factset_auth()
        url = f"{_FACTSET_BASE}/estimates/rolling/v3/consensus"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "ids": [f"{sym}-US"],
                        "metrics": ["EPS", "SALES"],
                        "periodicity": "ANNUAL",
                        "fiscalPeriodStart": "0FY",
                        "fiscalPeriodEnd": "2FY",
                    },
                    auth=auth,  # type: ignore[arg-type]
                )
                if resp.status_code == 404:
                    return {}
                resp.raise_for_status()
                data = resp.json()

            result = {
                "symbol": sym,
                "consensus": data.get("data", []),
                "source": "factset",
                "as_of": datetime.now(UTC).isoformat(),
            }
            await _cache_set(cache_key, json.dumps(result))
            return result
        except Exception:
            logger.exception("factset.get_estimates.error", symbol=sym)
            return {}
