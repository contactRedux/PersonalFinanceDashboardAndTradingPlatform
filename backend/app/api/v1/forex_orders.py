"""
OANDA Forex Orders REST API router.

Endpoints:
  POST   /api/v1/orders/forex          — place a forex order via OANDA
  GET    /api/v1/orders/forex          — list open OANDA forex orders
  DELETE /api/v1/orders/forex/{id}     — cancel an open OANDA forex order

Kill-switch check: all POST requests are rejected with 503 when the
platform-wide kill-switch is active.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser
from app.services.kill_switch import KillSwitch
from app.services.orders.oanda_order_service import (
    OANDAOrderRequest,
    cancel_forex_order,
    get_open_forex_orders,
    place_forex_order,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

_kill_switch = KillSwitch()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class PlaceForexOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=10, description="e.g. EUR_USD or EUR/USD")
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field("market", pattern="^(market|limit|stop)$")
    units: float = Field(..., gt=0, description="Number of units (positive; direction set by side)")
    price: float | None = Field(None, gt=0, description="Required for limit/stop orders")
    stop_loss_price: float | None = Field(None, gt=0)
    take_profit_price: float | None = Field(None, gt=0)
    time_in_force: str = Field("GTC", pattern="^(GTC|GTD|GFD|IOC|FOK)$")


class ForexOrderResponse(BaseModel):
    order_id: str
    instrument: str
    side: str
    order_type: str
    units: float
    status: str
    fill_price: float | None
    filled_at: str | None


class ForexOrderListResponse(BaseModel):
    orders: list[ForexOrderResponse]
    count: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _to_response(result) -> ForexOrderResponse:  # type: ignore[no-untyped-def]
    return ForexOrderResponse(
        order_id=result.order_id,
        instrument=result.instrument,
        side=result.side,
        order_type=result.order_type,
        units=result.units,
        status=result.status,
        fill_price=result.fill_price,
        filled_at=result.filled_at.isoformat() if result.filled_at else None,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post("", response_model=ForexOrderResponse, status_code=status.HTTP_201_CREATED)
async def place_forex_order_endpoint(
    body: PlaceForexOrderRequest,
    current_user: CurrentUser,
):
    """
    Place a forex order via OANDA.

    Rejects with 503 when the platform kill-switch is active.
    Falls back to simulated fill when OANDA credentials are absent.
    """
    if await _kill_switch.is_active():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order submissions are currently halted by the platform kill-switch.",
        )

    req = OANDAOrderRequest(
        user_id=current_user["sub"],
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        units=body.units,
        price=body.price,
        stop_loss_price=body.stop_loss_price,
        take_profit_price=body.take_profit_price,
        time_in_force=body.time_in_force,
    )

    try:
        result = await place_forex_order(req)
    except Exception as exc:  # noqa: BLE001
        logger.error("orders.forex.place.error", exc=str(exc), symbol=body.symbol)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Forex order submission failed.",
        ) from exc

    return _to_response(result)


@router.get("", response_model=ForexOrderListResponse)
async def list_forex_orders(
    current_user: CurrentUser,  # noqa: ARG001
    instrument: str | None = Query(None, description="Filter by instrument, e.g. EUR_USD"),
):
    """List open OANDA forex orders."""
    orders = await get_open_forex_orders(instrument=instrument)
    return ForexOrderListResponse(orders=[_to_response(o) for o in orders], count=len(orders))


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_forex_order_endpoint(
    order_id: str,
    current_user: CurrentUser,  # noqa: ARG001
):
    """Cancel an open OANDA forex order."""
    success = await cancel_forex_order(order_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel order at OANDA.",
        )
    return None
