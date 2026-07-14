"""
Orders REST API router.

Endpoints:
  POST   /api/v1/orders          — place a new order
  GET    /api/v1/orders          — list open orders (optionally filter by symbol)
  GET    /api/v1/orders/{id}     — get a specific order
  DELETE /api/v1/orders/{id}     — cancel an order
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models.order import Order
from app.services.orders.service import (
    OrderRequest,
    cancel_order,
    place_order,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field("market", pattern="^(market|limit|stop|stop_limit)$")
    quantity: float = Field(..., gt=0)
    limit_price: float | None = Field(None, gt=0)
    stop_price: float | None = Field(None, gt=0)
    time_in_force: str = Field("day", pattern="^(day|gtc|ioc|fok)$")


class OrderResponse(BaseModel):
    id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    status: str
    filled_qty: float
    filled_avg_price: float | None
    limit_price: float | None
    stop_price: float | None
    submitted_at: str
    created_at: str


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    count: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _db_order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=str(order.broker_order_id or order.id),
        client_order_id=str(order.client_order_id or ""),
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        status=order.status,
        filled_qty=order.filled_qty,
        filled_avg_price=order.filled_avg_price,
        limit_price=order.limit_price,
        stop_price=order.stop_price,
        submitted_at=order.submitted_at.isoformat() if order.submitted_at else "",
        created_at=order.created_at.isoformat(),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order_endpoint(
    body: PlaceOrderRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Place a new order via Alpaca paper trading.

    Persists the order to the local database and submits to Alpaca.
    Falls back to simulated fill if Alpaca keys are not configured.
    """
    req = OrderRequest(
        user_id=current_user["sub"],
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        quantity=body.quantity,
        limit_price=body.limit_price,
        stop_price=body.stop_price,
        time_in_force=body.time_in_force,
    )

    try:
        result = await place_order(req)
    except Exception as exc:  # noqa: BLE001
        logger.error("orders.place.error", exc=str(exc), symbol=body.symbol)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Order submission failed.",
        ) from exc

    # Persist to DB
    order = Order(
        user_id=current_user["sub"],
        client_order_id=result.client_order_id,
        broker_order_id=result.order_id,
        symbol=result.symbol,
        asset_class="equity",
        side=result.side,
        order_type=result.order_type,
        time_in_force=body.time_in_force,
        quantity=result.quantity,
        limit_price=result.limit_price,
        stop_price=result.stop_price,
        status=result.status,
        filled_qty=result.filled_qty,
        filled_avg_price=result.filled_avg_price,
        submitted_at=result.submitted_at,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    logger.info(
        "orders.placed",
        user_id=current_user["sub"],
        symbol=result.symbol,
        side=result.side,
        qty=result.quantity,
        status=result.status,
    )

    return _db_order_to_response(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    current_user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(None, description="Filter by symbol"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
):
    """List orders for the current user."""
    stmt = select(Order).where(Order.user_id == current_user["sub"])
    if symbol:
        stmt = stmt.where(Order.symbol == symbol.upper())
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc()).limit(200)

    result = await db.execute(stmt)
    orders = list(result.scalars().all())
    return OrderListResponse(
        orders=[_db_order_to_response(o) for o in orders],
        count=len(orders),
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, current_user: CurrentUser, db: DBSession):
    """Get a specific order by its ID."""
    result = await db.execute(
        select(Order).where(
            Order.user_id == current_user["sub"],
            Order.broker_order_id == order_id,
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return _db_order_to_response(order)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order_endpoint(order_id: str, current_user: CurrentUser, db: DBSession):
    """Cancel an open order."""
    result = await db.execute(
        select(Order).where(
            Order.user_id == current_user["sub"],
            Order.broker_order_id == order_id,
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if order.status in ("filled", "cancelled", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel order with status '{order.status}'.",
        )

    success = await cancel_order(order.broker_order_id or order_id)
    if success:
        order.status = "cancelled"
        order.cancelled_at = datetime.now(UTC)
        await db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cancel order at broker.",
        )
    return None
