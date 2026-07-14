"""
WebSocket — Time & Sales tape feed.

Streams real-time trade prints from channel:tape (all symbols)
or channel:tape:{symbol} (per-symbol filtered).
"""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.jwt import decode_access_token
from app.data.cache.redis_client import get_redis_pool

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/tape")
async def tape_feed(websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    subscribed: set[str] = set()
    redis = await get_redis_pool()
    pubsub = redis.pubsub()

    # Default: subscribe to the global tape
    await pubsub.subscribe("channel:tape")

    async def _read_client():
        try:
            async for data in websocket.iter_json():
                action = data.get("action")
                symbols = [s.upper() for s in data.get("symbols", [])]
                if action == "subscribe" and symbols:
                    for sym in symbols:
                        if sym not in subscribed:
                            await pubsub.subscribe(f"channel:tape:{sym}")
                            subscribed.add(sym)
                elif action == "unsubscribe" and symbols:
                    for sym in symbols:
                        if sym in subscribed:
                            await pubsub.unsubscribe(f"channel:tape:{sym}")
                            subscribed.discard(sym)
        except WebSocketDisconnect:
            pass

    async def _push_tape():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_json(json.loads(message["data"]))
                    except (json.JSONDecodeError, RuntimeError):
                        break
        except Exception:  # noqa: BLE001
            logger.debug("ws.tape.push_error")

    try:
        await asyncio.gather(_read_client(), _push_tape())
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.aclose()
