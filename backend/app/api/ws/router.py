"""WebSocket router — aggregates all WS endpoints."""
from fastapi import APIRouter

from app.api.ws import alerts_feed, market_feed, orderbook_feed, tape_feed

ws_router = APIRouter()

ws_router.include_router(market_feed.router)
ws_router.include_router(tape_feed.router)
ws_router.include_router(orderbook_feed.router)
ws_router.include_router(alerts_feed.router)
