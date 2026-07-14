"""WebSocket router — aggregates all WS endpoints."""

from fastapi import APIRouter, Query, WebSocket

from app.api.ws import alerts_feed, market_feed, orderbook_feed, tape_feed
from app.api.ws.orders_feed import orders_ws_endpoint

ws_router = APIRouter()

ws_router.include_router(market_feed.router)
ws_router.include_router(tape_feed.router)
ws_router.include_router(orderbook_feed.router)
ws_router.include_router(alerts_feed.router)


@ws_router.websocket("/ws/orders")
async def orders_feed(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """Live order status updates for the authenticated user."""
    await orders_ws_endpoint(websocket, token)
