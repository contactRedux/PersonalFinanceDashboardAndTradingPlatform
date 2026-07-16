"""
Yahoo Finance news adapter.

Fetches the latest news articles for a symbol using the yfinance library,
which is already a project dependency.

The `yf.Ticker(symbol).news` property returns a list of dicts with keys:
  uuid, title, publisher, link, providerPublishTime, type, relatedTickers, ...

This adapter normalises those dicts to the standard news aggregator schema.

No API key required. No rate limit documented by yfinance, but results are
cached in Redis for 30 minutes to reduce redundant calls.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger(__name__)

_CACHE_TTL = 60 * 30  # 30 minutes
_MAX_ARTICLES = 20


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

class YahooNewsAdapter:
    """
    Fetches up to 20 recent news articles from Yahoo Finance via yfinance.

    No authentication required. Results are cached in Redis for 30 minutes.

    Each returned article:
      headline, source="yahoo_finance", url, published_at, tickers_mentioned
    """

    async def get_articles(self, symbol: str) -> list[dict]:
        """
        Fetch the latest news articles for `symbol` from Yahoo Finance.

        Parameters
        ----------
        symbol : Ticker symbol, e.g. "AAPL"

        Returns a list of up to 20 article dicts in the standard aggregator schema.
        Returns [] on error or when yfinance returns no news.
        """
        sym = symbol.upper()
        cache_key = f"yahoo_news:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            articles = await self._fetch(sym)
            await _cache_set(cache_key, json.dumps(articles))
            return articles
        except Exception:  # noqa: BLE001
            logger.debug("yahoo_news.fetch_error", symbol=sym)
            return []

    async def _fetch(self, symbol: str) -> list[dict]:
        def _sync_fetch() -> list[dict]:
            import yfinance as yf  # noqa: PLC0415
            ticker = yf.Ticker(symbol)
            news_raw = ticker.news or []
            return news_raw[:_MAX_ARTICLES]

        news_raw = await asyncio.to_thread(_sync_fetch)
        now_iso = datetime.now(UTC).isoformat()
        articles = []

        for item in news_raw:
            # providerPublishTime is a Unix timestamp (int)
            pub_ts = item.get("providerPublishTime")
            if pub_ts:
                try:
                    published_at = datetime.fromtimestamp(int(pub_ts), tz=UTC).isoformat()
                except (ValueError, OSError):
                    published_at = now_iso
            else:
                published_at = now_iso

            # yfinance>=0.2.x returns content nested under "content" key
            content = item.get("content", {}) if isinstance(item.get("content"), dict) else {}
            title = (
                content.get("title")
                or item.get("title", "")
            )
            url = (
                content.get("canonicalUrl", {}).get("url")
                or content.get("clickThroughUrl", {}).get("url")
                or item.get("link", "")
            )
            publisher = (
                content.get("provider", {}).get("displayName")
                or item.get("publisher", "Yahoo Finance")
            )

            articles.append({
                "headline": str(title)[:500],
                "source": "yahoo_finance",
                "source_id": item.get("uuid", ""),
                "url": url,
                "published_at": published_at,
                "publisher": publisher,
                "tickers_mentioned": [symbol],
            })

        return articles

    async def get_news(self, symbol: str, limit: int = 20) -> list[dict]:
        """
        News-aggregator-compatible interface.
        Returns a list of article dicts with standard keys.
        """
        articles = await self.get_articles(symbol)
        return articles[:limit]
