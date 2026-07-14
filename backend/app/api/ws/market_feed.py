"""
WebSocket — Real-time market quotes fan-out.

Clients subscribe/unsubscribe to symbols. The handler subscribes to the
Redis channel:quotes pub/sub channel and forwards matching symbol updates.

Protocol:
  Client → Server:  {"action": "subscribe",   "symbols": ["AAPL", "BTC-USD"]}
  Client → Server:  {"action": "unsubscribe",  "symbols": ["AAPL"]}
  Server → Client:  {"type": "quote", "symbol": ..., "price": ..., ...}
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


@router.websocket("/ws/market")
async def market_feed(websocket: WebSocket, token: str = Query(...)):
    # Validate JWT before accepting the connection
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    subscribed: set[str] = set()
    redis = await get_redis_pool()
    pubsub = redis.pubsub()

    async def _read_client():
        """Read subscription commands from the client."""
        try:
            async for data in websocket.iter_json():
                action = data.get("action")
                symbols = [s.upper() for s in data.get("symbols", [])]
                if action == "subscribe" and symbols:
                    for sym in symbols:
                        if sym not in subscribed:
                            await pubsub.subscribe(f"channel:quotes:{sym}")
                            subscribed.add(sym)
                elif action == "unsubscribe" and symbols:
                    for sym in symbols:
                        if sym in subscribed:
                            await pubsub.unsubscribe(f"channel:quotes:{sym}")
                            subscribed.discard(sym)
        except WebSocketDisconnect:
            pass

    async def _push_quotes():
        """Forward Redis pub/sub messages to the WebSocket client."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload_data = json.loads(message["data"])
                        await websocket.send_json(payload_data)
                    except (json.JSONDecodeError, RuntimeError):
                        break
        except Exception:  # noqa: BLE001
            logger.debug("ws.market.push_error")

    try:
        await asyncio.gather(_read_client(), _push_quotes())
    except WebSocketDisconnect:
        pass
    finally:
        if subscribed:
            await pubsub.unsubscribe(*[f"channel:quotes:{s}" for s in subscribed])
        await pubsub.aclose()
        logger.info("ws.market.disconnect", user=payload.get("sub"), symbols=list(subscribed))
