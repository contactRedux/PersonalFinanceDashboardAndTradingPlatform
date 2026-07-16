"""
OpenFIGI adapter — free Bloomberg Open Symbology identifier mapping.

Maps ticker + exchange to FIGI, ISIN, CUSIP, SEDOL, and security metadata.
No license required; an optional API key raises the rate limit.

OpenFIGI API:
  POST https://api.openfigi.com/v3/mapping

Rate limits:
  Without key: 10 requests / minute, max 5 items per request
  With key:    25 requests / minute, max 100 items per request

Identifiers returned:
  figi          — Financial Instrument Global Identifier (Bloomberg)
  isin          — International Securities Identification Number
  cusip         — Committee on Uniform Securities Identification Procedures
  sedol         — Stock Exchange Daily Official List (LSE)
  name          — Full security name
  securityType  — Common Stock, ETF, etc.
  marketSector  — Equity, Fixed Income, etc.

Results are cached in Redis for 24 hours (FIGI identifiers are stable).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
_CACHE_TTL = 60 * 60 * 24  # 24 hours


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


# ─── Adapter ──────────────────────────────────────────────────────────────────

class OpenFIGIAdapter:
    """
    Maps ticker symbols to Bloomberg FIGI and cross-identifiers (ISIN, CUSIP, SEDOL).

    Usage:
        adapter = OpenFIGIAdapter()
        result = await adapter.map_identifiers("AAPL", exchange="US")
        # → {"figi": "BBG000B9Y5X2", "isin": "US0378331005", "cusip": "037833100", ...}

    Returns an empty dict when the API is unreachable or returns no data.
    """

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.openfigi_api_key:
            headers["X-OPENFIGI-APIKEY"] = settings.openfigi_api_key
        return headers

    async def map_identifiers(self, ticker: str, exchange: str = "US") -> dict:
        """
        Map a single ticker + exchange to FIGI/ISIN/CUSIP/SEDOL.

        Parameters
        ----------
        ticker   : e.g. "AAPL", "MSFT"
        exchange : two-letter MIC or OpenFIGI exchange code (default: "US" = NYSE/NASDAQ)

        Returns a flat dict with: figi, isin, cusip, sedol, name, securityType,
        marketSector, ticker, exchange, source="openfigi".
        Returns {} on error or no match.
        """
        sym = ticker.upper()
        exc = exchange.upper()
        cache_key = f"openfigi:map:{sym}:{exc}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            result = await self._fetch_single(sym, exc)
            await _cache_set(cache_key, json.dumps(result))
            return result
        except Exception:  # noqa: BLE001
            logger.debug("openfigi.map_identifiers.error", ticker=sym, exchange=exc)
            return {}

    async def _fetch_single(self, ticker: str, exchange: str) -> dict:
        payload = [{"idType": "TICKER", "idValue": ticker, "exchCode": exchange}]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _OPENFIGI_URL,
                json=payload,
                headers=self._headers(),
            )

        if resp.status_code == 429:
            logger.debug("openfigi.rate_limited", ticker=ticker)
            return {}

        if resp.status_code != 200:
            logger.debug(
                "openfigi.http_error", ticker=ticker, status=resp.status_code
            )
            return {}

        data = resp.json()
        if not data or "data" not in data[0]:
            return {}

        matches = data[0]["data"]
        if not matches:
            return {}

        # Take the first match (most relevant)
        m = matches[0]
        return {
            "figi": m.get("figi", ""),
            "isin": m.get("isin", ""),
            "cusip": m.get("cusip", ""),
            "sedol": m.get("sedol", ""),
            "name": m.get("name", ""),
            "securityType": m.get("securityType", ""),
            "securityType2": m.get("securityType2", ""),
            "marketSector": m.get("marketSector", ""),
            "ticker": ticker,
            "exchange": exchange,
            "source": "openfigi",
            "as_of": datetime.now(UTC).isoformat(),
        }

    async def enrich_search_results(self, results: list[dict]) -> list[dict]:
        """
        Enrich a list of search result dicts with FIGI/ISIN/CUSIP identifiers.

        Each result dict is expected to have at least a "symbol" key.
        Identifier lookup is performed per-symbol; failures are silently skipped.

        Returns the same list with each dict updated in-place with identifier fields.
        """
        import asyncio  # noqa: PLC0415

        async def _enrich_one(item: dict) -> dict:
            sym = item.get("symbol", "")
            exchange = item.get("exchange", "US")
            if not sym:
                return item
            identifiers = await self.map_identifiers(sym, exchange=exchange)
            if identifiers:
                item.update({
                    "figi": identifiers.get("figi"),
                    "isin": identifiers.get("isin"),
                    "cusip": identifiers.get("cusip"),
                    "sedol": identifiers.get("sedol"),
                })
            return item

        enriched = await asyncio.gather(*[_enrich_one(r) for r in results])
        return list(enriched)
