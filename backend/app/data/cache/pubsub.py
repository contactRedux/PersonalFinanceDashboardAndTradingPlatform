"""
Redis pub/sub helpers for WebSocket fan-out.

Pattern:
  - Data ingestion services PUBLISH to channel:quotes:{symbol}
  - WebSocket handlers SUBSCRIBE and forward to connected clients
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from app.data.cache.redis_client import get_redis_pool

CHANNEL_QUOTES = "channel:quotes"
CHANNEL_TAPE = "channel:tape"
CHANNEL_ORDERBOOK = "channel:orderbook:{symbol}"
CHANNEL_ALERTS = "channel:alerts:{user_id}"


async def publish(channel: str, payload: dict) -> None:
    """Publish a JSON payload to a Redis channel."""
    redis = await get_redis_pool()
    await redis.publish(channel, json.dumps(payload))


async def subscribe_channel(channel: str) -> AsyncGenerator[dict, None]:
    """
    Subscribe to a Redis pub/sub channel and yield decoded JSON messages.
    Uses a dedicated connection (not the shared pool) per subscription.
    """
    redis = await get_redis_pool()
    # Create a dedicated pub/sub connection
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
