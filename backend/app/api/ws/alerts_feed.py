"""
WebSocket — Per-user alert notifications.

Streams triggered alert events to the authenticated user.
channel:alerts:{user_id}
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.data.cache.redis_client import get_redis_pool

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/alerts")
async def alerts_feed(websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return

    user_id = payload.get("sub")
    await websocket.accept()

    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    channel = f"channel:alerts:{user_id}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_json(json.loads(message["data"]))
                except (json.JSONDecodeError, RuntimeError):
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info("ws.alerts.disconnect", user=user_id)
