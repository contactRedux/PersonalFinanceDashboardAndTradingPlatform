"""
EarningsCall.ai adapter — AI-summarized earnings call transcripts.

API: https://earningscall.biz/api
Free tier: limited transcript access (recent quarters for major tickers).
No code changes needed to upgrade — just swap the API key.

Falls back gracefully when EARNINGSCALL_API_KEY is absent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_EARNINGSCALL_BASE = "https://v2.api.earningscall.biz"
_CACHE_TTL = 60 * 60 * 24  # 24 hours — transcripts don't change
_TIMEOUT = 15.0


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

class EarningsCallAdapter:
    """
    Fetches earnings call transcripts from EarningsCall.ai.

    Free tier returns the most recent transcript per ticker.
    Paid tier (Individual $9/mo) gives 1,000 transcript requests/month with
    full historical access.
    """

    async def get_recent_transcripts(
        self,
        symbol: str,
        limit: int = 4,
    ) -> list[dict]:
        """
        Return the most recent earnings call transcripts for a symbol.
        Each item: { symbol, year, quarter, title, text, date, source }
        Returns [] when key is absent or on error.
        """
        if not settings.earningscall_api_key:
            return []

        sym = symbol.upper()
        cache_key = f"earningscall:recent:{sym}:{limit}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                import json  # noqa: PLC0415
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            result = await self._fetch_events(sym, limit)
        except Exception:  # noqa: BLE001
            logger.debug("earningscall.fetch_error", symbol=sym)
            return []

        import json  # noqa: PLC0415
        await _cache_set(cache_key, json.dumps(result))
        return result

    async def get_transcript(
        self,
        symbol: str,
        year: int,
        quarter: int,
    ) -> dict | None:
        """
        Fetch a specific transcript by year/quarter.
        Returns the transcript dict or None on error/not found.
        """
        if not settings.earningscall_api_key:
            return None

        sym = symbol.upper()
        cache_key = f"earningscall:transcript:{sym}:{year}:Q{quarter}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                import json  # noqa: PLC0415
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            result = await self._fetch_transcript(sym, year, quarter)
        except Exception:  # noqa: BLE001
            logger.debug("earningscall.transcript_error", symbol=sym, year=year, quarter=quarter)
            return None

        if result:
            import json  # noqa: PLC0415
            await _cache_set(cache_key, json.dumps(result))
        return result

    async def _fetch_events(self, symbol: str, limit: int) -> list[dict]:
        """Fetch the list of available transcripts for a symbol."""
        params = {"apikey": settings.earningscall_api_key}
        now_iso = datetime.now(UTC).isoformat()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_EARNINGSCALL_BASE}/events",
                params={**params, "exchange": "NASDAQ,NYSE", "ticker": symbol},
            )

        if resp.status_code in (401, 402, 403):
            logger.debug("earningscall.auth_error", symbol=symbol, status=resp.status_code)
            return []

        if resp.status_code != 200:
            logger.debug("earningscall.http_error", symbol=symbol, status=resp.status_code)
            return []

        data = resp.json()
        events = data if isinstance(data, list) else (data.get("events") or [])

        results = []
        for event in events[:limit]:
            results.append({
                "symbol": symbol,
                "year": event.get("year"),
                "quarter": event.get("quarter"),
                "title": f"{symbol} Q{event.get('quarter', '?')} {event.get('year', '')} Earnings Call",
                "date": event.get("conferenceDate") or event.get("date", ""),
                "has_transcript": bool(event.get("hasTranscript")),
                "source": "earningscall",
                "created_at": now_iso,
            })

        return results

    async def _fetch_transcript(self, symbol: str, year: int, quarter: int) -> dict | None:
        """Fetch a single transcript."""
        params = {
            "apikey": settings.earningscall_api_key,
            "exchange": "NASDAQ,NYSE",
            "ticker": symbol,
            "year": year,
            "quarter": quarter,
        }
        now_iso = datetime.now(UTC).isoformat()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_EARNINGSCALL_BASE}/transcript",
                params=params,
            )

        if resp.status_code in (401, 402, 403, 404):
            logger.debug(
                "earningscall.transcript_unavailable",
                symbol=symbol, year=year, quarter=quarter, status=resp.status_code,
            )
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()
        return {
            "symbol": symbol,
            "year": year,
            "quarter": quarter,
            "title": f"{symbol} Q{quarter} {year} Earnings Call",
            "text": data.get("text") or data.get("transcript", ""),
            "speakers": data.get("speakers", []),
            "date": data.get("conferenceDate", ""),
            "source": "earningscall",
            "created_at": now_iso,
        }

    async def get_news(self, symbol: str, limit: int = 4) -> list[dict]:
        """
        News-aggregator-compatible interface.
        Returns recent transcript entries as article dicts.
        """
        transcripts = await self.get_recent_transcripts(symbol, limit=limit)
        now_iso = datetime.now(UTC).isoformat()
        articles = []
        for t in transcripts:
            articles.append({
                "headline": t.get("title", f"{symbol} Earnings Call"),
                "source": "earningscall",
                "source_id": f"{t.get('year')}-Q{t.get('quarter')}",
                "url": f"https://earningscall.biz/{symbol.lower()}",
                "published_at": t.get("date") or now_iso,
                "sentiment": None,
                "tickers_mentioned": [symbol],
                "body": t.get("text", "")[:500],
            })
        return articles
