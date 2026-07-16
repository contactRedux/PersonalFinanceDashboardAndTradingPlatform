"""
StockTwits adapter — social sentiment from the public cashtag stream.

The public stream endpoint requires no API key for read access (returns up to
30 most recent messages per request). An optional access token enables higher
rate limits and user-specific endpoints, but is not required.

Rate limit: 10 requests / minute (enforced via token bucket).
Results are cached in Redis for 15 minutes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_STOCKTWITS_BASE = "https://api.stocktwits.com/api/2"
_CACHE_TTL = 60 * 15  # 15 minutes
_REQUESTS_PER_MINUTE = 10.0
_REFILL_RATE = _REQUESTS_PER_MINUTE / 60.0  # tokens per second
_TIMEOUT = 8.0


# ─── Token bucket rate limiter ───────────────────────────────────────────────

class _TokenBucket:
    def __init__(self, capacity: float, refill_rate: float) -> None:
        self._capacity = capacity
        self._tokens = capacity
        self._refill_rate = refill_rate
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(
                self._capacity,
                self._tokens + (now - self._last) * self._refill_rate,
            )
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
            else:
                wait = (1 - self._tokens) / self._refill_rate
                await asyncio.sleep(wait)
                self._tokens = 0


_bucket = _TokenBucket(capacity=_REQUESTS_PER_MINUTE, refill_rate=_REFILL_RATE)


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

class StockTwitsAdapter:
    """
    Fetches the most recent messages for a symbol from the StockTwits
    public stream API.

    Each returned item:
      message, created_at, username, likes, sentiment ("Bullish"/"Bearish"/None),
      source="stocktwits"

    Also computes bullish_pct: fraction of sentiment-tagged messages that are
    bullish (0.0–1.0).
    """

    async def get_stream(
        self,
        symbol: str,
        max_results: int = 30,
    ) -> dict:
        """
        Fetch recent messages for `symbol`.
        Returns:
          { messages: [...], bullish_pct: float, message_count: int, symbol: str }
        """
        sym = symbol.upper()
        cache_key = f"stocktwits:stream:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                import json  # noqa: PLC0415
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            result = await self._fetch(sym, max_results)
        except Exception:  # noqa: BLE001
            logger.debug("stocktwits.fetch_error", symbol=sym)
            result = {"messages": [], "bullish_pct": 0.5, "message_count": 0, "symbol": sym}

        import json  # noqa: PLC0415
        await _cache_set(cache_key, json.dumps(result))
        return result

    async def _fetch(self, symbol: str, max_results: int) -> dict:
        await _bucket.acquire()

        headers: dict = {"Accept": "application/json"}
        # Optional: add Bearer token if configured
        if settings.stocktwits_access_token:
            headers["Authorization"] = f"OAuth {settings.stocktwits_access_token}"

        params: dict = {"filter": "all"}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_STOCKTWITS_BASE}/streams/symbol/{symbol}.json",
                params=params,
                headers=headers,
            )

        if resp.status_code == 429:
            logger.debug("stocktwits.rate_limited", symbol=symbol)
            return {"messages": [], "bullish_pct": 0.5, "message_count": 0, "symbol": symbol}

        if resp.status_code != 200:
            logger.debug("stocktwits.http_error", symbol=symbol, status=resp.status_code)
            return {"messages": [], "bullish_pct": 0.5, "message_count": 0, "symbol": symbol}

        data = resp.json()
        raw_messages = (data.get("messages") or [])[:max_results]

        now_iso = datetime.now(UTC).isoformat()
        messages = []
        bullish_count = 0
        bearish_count = 0

        for msg in raw_messages:
            sentiment_raw = (msg.get("entities") or {}).get("sentiment") or {}
            sentiment = sentiment_raw.get("basic")  # "Bullish" | "Bearish" | None

            if sentiment == "Bullish":
                bullish_count += 1
            elif sentiment == "Bearish":
                bearish_count += 1

            messages.append({
                "message": msg.get("body", ""),
                "created_at": msg.get("created_at", now_iso),
                "username": (msg.get("user") or {}).get("username", ""),
                "likes": (msg.get("likes") or {}).get("total", 0),
                "sentiment": sentiment,
                "source": "stocktwits",
            })

        tagged_total = bullish_count + bearish_count
        bullish_pct = (bullish_count / tagged_total) if tagged_total > 0 else 0.5

        return {
            "symbol": symbol,
            "messages": messages,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "bullish_pct": round(bullish_pct, 4),
            "message_count": len(messages),
            "tagged_count": tagged_total,
            "as_of": now_iso,
        }

    async def get_news(self, symbol: str, limit: int = 10) -> list[dict]:
        """
        News-aggregator-compatible interface.
        Returns a list of article dicts with standard keys.
        """
        stream = await self.get_stream(symbol, max_results=limit)
        articles = []
        for msg in stream.get("messages", []):
            articles.append({
                "headline": msg["message"][:200],
                "source": "stocktwits",
                "source_id": "",
                "url": f"https://stocktwits.com/{msg['username']}",
                "published_at": msg["created_at"],
                "sentiment": msg["sentiment"],
                "tickers_mentioned": [symbol],
            })
        return articles
