"""
Latest quote cache — thin Redis Hash wrapper.

Key structure:  quote:{symbol}  →  Hash of quote fields
TTL: 60 seconds (stale if provider goes offline)
"""
from __future__ import annotations

import json

from app.data.cache.redis_client import get_redis_pool

QUOTE_TTL = 60  # seconds


async def set_quote(symbol: str, quote: dict) -> None:
    redis = await get_redis_pool()
    key = f"quote:{symbol.upper()}"
    await redis.hset(key, mapping={k: str(v) for k, v in quote.items()})
    await redis.expire(key, QUOTE_TTL)


async def get_quote(symbol: str) -> dict | None:
    redis = await get_redis_pool()
    key = f"quote:{symbol.upper()}"
    data = await redis.hgetall(key)
    return data if data else None


async def get_quotes(symbols: list[str]) -> dict[str, dict | None]:
    """Batch fetch quotes for a list of symbols."""
    redis = await get_redis_pool()
    pipeline = redis.pipeline()
    for symbol in symbols:
        pipeline.hgetall(f"quote:{symbol.upper()}")
    results = await pipeline.execute()
    return {
        symbol: (data if data else None)
        for symbol, data in zip(symbols, results, strict=False)
    }


async def set_sentiment_cache(symbol: str, payload: dict, ttl: int = 300) -> None:
    redis = await get_redis_pool()
    await redis.setex(f"sentiment:{symbol.upper()}", ttl, json.dumps(payload))


async def get_sentiment_cache(symbol: str) -> dict | None:
    redis = await get_redis_pool()
    raw = await redis.get(f"sentiment:{symbol.upper()}")
    return json.loads(raw) if raw else None
