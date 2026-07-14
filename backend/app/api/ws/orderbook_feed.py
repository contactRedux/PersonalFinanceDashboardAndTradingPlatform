"""
WebSocket — Level 2 / Order Book feed for a specific symbol.

Streams order book snapshots from channel:orderbook:{symbol}.
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.data.cache.redis_client import get_redis_pool

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/orderbook/{symbol}")
async def orderbook_feed(symbol: str, websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    channel = f"channel:orderbook:{symbol.upper()}"
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
