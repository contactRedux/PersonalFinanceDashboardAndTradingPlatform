"""
WebSocket order-status feed.

Broadcasts live order status updates to authenticated clients.
Clients subscribe on connect; updates arrive from Redis pub/sub
whenever an order status changes (published by the order service).
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.data.cache.redis_client import get_redis_pool

logger = structlog.get_logger(__name__)

_ORDERS_CHANNEL_PREFIX = "orders:"


async def orders_ws_endpoint(websocket: WebSocket, token: str) -> None:
    """
    WebSocket handler for live order status updates.

    Connect: ws://host/ws/orders?token=<jwt>
    Messages pushed:
      {"type": "order_update", "order": {...}}
      {"type": "ping"}
    """
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=1008)  # Policy Violation
        return

    user_id: str = payload["sub"]
    await websocket.accept()
    logger.info("orders_ws.connected", user_id=user_id)

    channel = f"{_ORDERS_CHANNEL_PREFIX}{user_id}"
    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    ping_interval = 30  # seconds

    try:

        async def reader() -> None:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"])
                    except Exception:  # noqa: BLE001
                        break

        async def pinger() -> None:
            while True:
                await asyncio.sleep(ping_interval)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:  # noqa: BLE001
                    break

        await asyncio.gather(reader(), pinger(), return_exceptions=True)

    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        logger.info("orders_ws.disconnected", user_id=user_id)


async def publish_order_update(user_id: str, order_data: dict) -> None:
    """Publish an order status update to the user's WebSocket channel."""
    redis = await get_redis_pool()
    channel = f"{_ORDERS_CHANNEL_PREFIX}{user_id}"
    payload = json.dumps({"type": "order_update", "order": order_data})
    await redis.publish(channel, payload)
