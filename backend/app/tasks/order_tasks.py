"""
Celery task — periodic Alpaca order status synchronisation.

Polls the Alpaca paper trading API every 10 seconds for open orders.
When a fill or cancellation is detected, updates the local PostgreSQL record
and publishes the change to the Redis pub/sub channel so the /ws/orders
WebSocket feed delivers the update to the connected client.

When Alpaca keys are absent (demo mode), the task is a no-op.
"""

from __future__ import annotations

import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

# ─── Terminal order statuses — no further polling needed ──────────────────────
_TERMINAL_STATUSES = frozenset({"filled", "cancelled", "rejected", "expired"})


@celery_app.task(
    name="order_tasks.sync_open_orders",
    bind=False,
    max_retries=0,  # beat fires every 10s; don't stack retries
)
def sync_open_orders() -> dict:
    """
    Fetch all open orders from Alpaca, compare against local DB, and publish
    any status changes via Redis pub/sub.

    Returns a summary dict with counts of orders checked and updated.
    """
    try:
        return asyncio.run(_sync())
    except Exception:  # noqa: BLE001
        logger.exception("order_tasks.sync_open_orders.error")
        return {"checked": 0, "updated": 0, "skipped": "error"}


async def _sync() -> dict:
    """Async implementation — runs inside asyncio.run() from the sync Celery task."""
    from app.api.ws.orders_feed import publish_order_update  # noqa: PLC0415
    from app.database import AsyncSessionLocal  # noqa: PLC0415
    from app.services.orders.service import _is_alpaca_available  # noqa: PLC0415

    if not _is_alpaca_available():
        logger.debug("order_tasks.sync.skipped", reason="no_alpaca_keys")
        return {"checked": 0, "updated": 0, "skipped": "no_alpaca_keys"}

    alpaca_orders = await _fetch_alpaca_open_orders()
    if not alpaca_orders:
        return {"checked": 0, "updated": 0}

    updated = 0
    async with AsyncSessionLocal() as session:
        for alpaca_order in alpaca_orders:
            was_updated = await _process_order(session, alpaca_order, publish_order_update)
            if was_updated:
                updated += 1

    return {"checked": len(alpaca_orders), "updated": updated}


async def _fetch_alpaca_open_orders() -> list[dict]:
    """GET /v2/orders?status=open from Alpaca paper trading API."""
    import httpx  # noqa: PLC0415

    from app.services.orders.service import _alpaca_headers  # noqa: PLC0415

    _paper_base = "https://paper-api.alpaca.markets"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_paper_base}/v2/orders",
                headers=_alpaca_headers(),
                params={"status": "open", "limit": 100},
            )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(
            "order_tasks.alpaca_fetch_failed",
            status_code=resp.status_code,
        )
    except Exception:  # noqa: BLE001
        logger.exception("order_tasks.alpaca_fetch_error")
    return []


async def _process_order(session, alpaca_order: dict, publish_fn) -> bool:
    """
    Compare one Alpaca order against the local DB record.
    If the status changed, update the record and publish via Redis.
    Returns True when an update was written.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from app.models.order import Order  # noqa: PLC0415

    broker_order_id: str = alpaca_order["id"]
    new_status: str = alpaca_order["status"]

    result = await session.execute(
        select(Order).where(Order.broker_order_id == broker_order_id)
    )
    order: Order | None = result.scalar_one_or_none()

    if order is None:
        # Order placed outside this session; skip.
        return False

    if order.status == new_status:
        # No change.
        return False

    # Apply update
    order.status = new_status
    order.filled_qty = float(alpaca_order.get("filled_qty") or 0)
    if alpaca_order.get("filled_avg_price"):
        order.filled_avg_price = float(alpaca_order["filled_avg_price"])

    if new_status == "filled" and order.filled_at is None:
        order.filled_at = datetime.now(UTC)
    if new_status == "cancelled" and order.cancelled_at is None:
        order.cancelled_at = datetime.now(UTC)

    await session.commit()

    # Trigger AI trade journal analysis for filled orders
    if new_status == "filled":
        try:
            from app.tasks.journal_tasks import analyze_trade  # noqa: PLC0415

            analyze_trade.delay(str(order.id))
        except Exception:  # noqa: BLE001
            logger.debug("order_tasks.journal_dispatch_skipped", order_id=str(order.id))

        # Update portfolio positions table via handle_order_fill task
        try:
            from app.tasks.fill_tasks import handle_order_fill  # noqa: PLC0415

            handle_order_fill.delay(
                symbol=order.symbol,
                side=order.side,
                filled_qty=order.filled_qty,
                filled_avg_price=order.filled_avg_price or 0.0,
                user_id=str(order.user_id),
            )
        except Exception:  # noqa: BLE001
            logger.debug("order_tasks.fill_dispatch_skipped", order_id=str(order.id))

    # Publish to Redis → /ws/orders WebSocket
    order_data = {
        "id": str(order.broker_order_id or order.id),
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "quantity": order.quantity,
        "status": order.status,
        "filled_qty": order.filled_qty,
        "filled_avg_price": order.filled_avg_price,
    }
    await publish_fn(str(order.user_id), order_data)

    logger.info(
        "order_tasks.order_updated",
        broker_order_id=broker_order_id,
        symbol=order.symbol,
        new_status=new_status,
    )
    return True
