"""
Celery task — handle_order_fill.

Invoked when an Alpaca order-fill WebSocket event is received.
Updates the `positions` table in PostgreSQL:
  - Buy fill: increment quantity (or create position if not present)
  - Sell fill: decrement quantity; remove position when quantity reaches zero

This task is also triggered by the existing sync_open_orders path when a
fill is detected via polling, so it consolidates position-book logic.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import structlog

from app.database import AsyncSessionLocal
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="fill_tasks.handle_order_fill",
    bind=False,
    max_retries=3,
    default_retry_delay=5,
)
def handle_order_fill(
    symbol: str,
    side: str,
    filled_qty: float,
    filled_avg_price: float,
    user_id: str,
) -> dict:
    """
    Update the portfolio positions table when an order fill is received.

    Parameters
    ----------
    symbol : str
        Ticker symbol (e.g. "AAPL").
    side : str
        "buy" or "sell".
    filled_qty : float
        Number of shares/contracts filled.
    filled_avg_price : float
        Average fill price.
    user_id : str
        UUID string of the owning user (used to find the default portfolio).

    Returns
    -------
    dict
        {"action": "opened"|"updated"|"closed"|"skipped", "symbol": symbol}
    """
    try:
        return asyncio.run(
            _apply_fill(symbol, side, filled_qty, filled_avg_price, user_id)
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "fill_tasks.handle_order_fill.error",
            symbol=symbol,
            side=side,
            user_id=user_id,
        )
        return {"action": "error", "symbol": symbol}


async def _apply_fill(
    symbol: str,
    side: str,
    filled_qty: float,
    filled_avg_price: float,
    user_id: str,
) -> dict:
    """Async implementation — runs inside asyncio.run() from the Celery task."""
    import uuid  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from app.models.portfolio import Portfolio, Position  # noqa: PLC0415

    qty = Decimal(str(filled_qty))
    price = Decimal(str(filled_avg_price))

    async with AsyncSessionLocal() as session:
        # Resolve a portfolio for this user (use the first one found)
        uid = uuid.UUID(user_id)
        result = await session.execute(
            select(Portfolio).where(Portfolio.user_id == uid).limit(1)
        )
        portfolio: Portfolio | None = result.scalar_one_or_none()
        if portfolio is None:
            logger.warning("fill_tasks.no_portfolio", user_id=user_id, symbol=symbol)
            return {"action": "skipped", "symbol": symbol}

        # Find existing open position for this symbol
        pos_result = await session.execute(
            select(Position).where(
                Position.portfolio_id == portfolio.id,
                Position.symbol == symbol.upper(),
                Position.is_open == True,  # noqa: E712
            )
        )
        position: Position | None = pos_result.scalar_one_or_none()

        if side == "buy":
            if position is None:
                # Open new long position
                position = Position(
                    portfolio_id=portfolio.id,
                    symbol=symbol.upper(),
                    asset_class="equity",
                    side="long",
                    quantity=qty,
                    avg_entry_price=price,
                    is_open=True,
                )
                session.add(position)
                action = "opened"
            else:
                # Average up/down into existing position
                total_qty = position.quantity + qty
                position.avg_entry_price = (
                    (position.avg_entry_price * position.quantity + price * qty) / total_qty
                )
                position.quantity = total_qty
                action = "updated"
        else:  # sell
            if position is None:
                logger.warning(
                    "fill_tasks.sell_without_position",
                    symbol=symbol,
                    user_id=user_id,
                )
                return {"action": "skipped", "symbol": symbol}

            new_qty = position.quantity - qty
            if new_qty <= Decimal("0"):
                # Position fully closed
                position.quantity = Decimal("0")
                position.is_open = False
                action = "closed"
            else:
                position.quantity = new_qty
                action = "updated"

        await session.commit()

        logger.info(
            "fill_tasks.position_updated",
            action=action,
            symbol=symbol,
            side=side,
            qty=str(qty),
            user_id=user_id,
        )
        return {"action": action, "symbol": symbol}
