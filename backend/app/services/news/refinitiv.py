"""
Reuters / Refinitiv news adapter.

This module is a **license-ready stub** — fully implemented but feature-flagged
on both the `REFINITIV_APP_KEY` environment variable AND the presence of the
`refinitiv-data` SDK (which requires a paid LSEG/Refinitiv license).

Activation:
  1. Obtain an LSEG/Refinitiv RDP license and App Key (see docs/adr/ADR-009).
  2. Install the SDK:
         pip install refinitiv-data>=1.0.0
         # or:
         uv pip install refinitiv-data>=1.0.0
  3. Set REFINITIV_APP_KEY in your .env file.

The adapter activates automatically on the next server restart — no code changes
needed.

When the SDK is not installed, the module logs a single debug message and all
methods return empty lists. No ImportError is raised.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_REFINITIV_SDK_AVAILABLE = False
_CACHE_TTL = 60 * 15  # 15 minutes

# ─── Try to import the SDK ────────────────────────────────────────────────────
try:
    import refinitiv.data as rd  # type: ignore[import-not-found]  # noqa: F401
    _REFINITIV_SDK_AVAILABLE = True
except ImportError:
    rd = None  # type: ignore[assignment]


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

class RefinitivAdapter:
    """
    Reuters / Refinitiv news adapter.

    Requires:
      - REFINITIV_APP_KEY to be set in config
      - `refinitiv-data` Python SDK to be installed (separate licensed install)

    Returns empty results gracefully when either requirement is not met.

    Each returned article:
      headline, source="refinitiv", url, published_at, tickers_mentioned, story_id
    """

    def _is_available(self) -> bool:
        return _REFINITIV_SDK_AVAILABLE and bool(settings.refinitiv_app_key)

    async def get_news(self, symbol: str, limit: int = 10) -> list[dict]:
        """
        Fetch recent Reuters news headlines for `symbol`.

        Returns a list of article dicts compatible with the news aggregator schema.
        Returns [] when the SDK is not installed or no App Key is configured.
        """
        if not self._is_available():
            if not _REFINITIV_SDK_AVAILABLE:
                logger.debug(
                    "refinitiv.sdk_not_installed",
                    hint="pip install refinitiv-data>=1.0.0",
                )
            else:
                logger.debug("refinitiv.no_app_key", symbol=symbol)
            return []

        sym = symbol.upper()
        cache_key = f"refinitiv:news:{sym}:{limit}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            articles = await self._fetch(sym, limit)
            await _cache_set(cache_key, json.dumps(articles))
            return articles
        except Exception:  # noqa: BLE001
            logger.debug("refinitiv.fetch_error", symbol=sym)
            return []

    async def _fetch(self, symbol: str, limit: int) -> list[dict]:
        """
        Call the Refinitiv Data Library to fetch news headlines.

        Uses `rd.get_news_headlines()` from the `refinitiv-data` SDK.
        Requires an open session (session is opened per-call to avoid state issues).
        """
        import asyncio  # noqa: PLC0415

        def _sync_fetch() -> list[dict]:
            rd.open_session(app_key=settings.refinitiv_app_key)  # type: ignore[union-attr]
            try:
                headlines = rd.get_news_headlines(  # type: ignore[union-attr]
                    query=symbol,
                    count=limit,
                )
                # headlines is a pandas DataFrame with columns:
                #   versionCreated, text, storyId, sourceCode
                if headlines is None or headlines.empty:
                    return []

                now_iso = datetime.now(UTC).isoformat()
                articles = []
                for _, row in headlines.iterrows():
                    published_at = (
                        row.get("versionCreated", now_iso)
                        if hasattr(row.get("versionCreated", ""), "isoformat")
                        else str(row.get("versionCreated", now_iso))
                    )
                    articles.append({
                        "headline": str(row.get("text", ""))[:500],
                        "source": "refinitiv",
                        "source_id": str(row.get("storyId", "")),
                        "url": f"https://www.refinitiv.com/en/news/{row.get('storyId', '')}",
                        "published_at": published_at,
                        "tickers_mentioned": [symbol],
                    })
                return articles[:limit]
            finally:
                try:
                    rd.close_session()  # type: ignore[union-attr]
                except Exception:  # noqa: BLE001
                    pass

        return await asyncio.to_thread(_sync_fetch)
