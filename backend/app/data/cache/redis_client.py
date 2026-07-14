"""
Redis connection pool — shared singleton, initialized on app startup.
Uses redis-py async client with hiredis parser.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import get_settings

_pool: Redis | None = None
settings = get_settings()


async def get_redis_pool() -> Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _pool


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
