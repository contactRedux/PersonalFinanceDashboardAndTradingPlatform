"""
Alert condition evaluation sweep.

Loads all active alerts from PostgreSQL, fetches current prices from the
Redis quote cache, evaluates each condition, marks triggered alerts in the DB,
and publishes triggered events to the Redis alerts channel so the WebSocket
feed delivers them to connected clients.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ─── Patchable module-level wrappers ──────────────────────────────────────────

async def get_quote(symbol: str) -> dict | None:
    """Fetch a cached quote. Module-level so tests can patch it."""
    from app.data.cache.quote_cache import get_quote as _gq  # noqa: PLC0415
    return await _gq(symbol)


@celery_app.task(name="tasks.evaluate_alerts")
def evaluate_alerts() -> dict:
    """Scan all active alerts and publish triggered ones to Redis."""
    try:
        return asyncio.run(_evaluate_async())
    except Exception:  # noqa: BLE001
        logger.exception("tasks.evaluate_alerts.error")
        return {"status": "error"}


async def _evaluate_async() -> dict:
    """Async implementation — runs inside asyncio.run() from the sync Celery task."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.data.cache.pubsub import CHANNEL_ALERTS, publish  # noqa: PLC0415
    from app.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.alert import Alert  # noqa: PLC0415
    # get_quote is the module-level patchable wrapper
    from app.services.alerts.evaluator import (  # noqa: PLC0415
        AlertCondition,
        AlertStatus,
        AlertType,
        evaluate_price_alert,
    )

    triggered_count = 0
    evaluated_count = 0

    async with AsyncSessionLocal() as session:
        # Load all active, un-triggered alerts
        result = await session.execute(
            select(Alert).where(
                Alert.is_active == True,  # noqa: E712
                Alert.triggered_at == None,  # noqa: E711
            )
        )
        alerts: list[Alert] = list(result.scalars().all())
        evaluated_count = len(alerts)

        # Gather unique symbols
        symbols = {a.symbol for a in alerts if a.symbol and a.symbol != "PORTFOLIO"}

        # Batch-fetch quotes from Redis
        quote_map: dict[str, dict] = {}
        for symbol in symbols:
            q = await get_quote(symbol)
            if q:
                # Redis stores everything as strings — coerce numeric fields
                quote_map[symbol] = {
                    "price": float(q.get("price", 0) or 0),
                    "change_pct": float(q.get("change_pct", 0) or 0),
                    "volume": float(q.get("volume", 0) or 0),
                    "volume_ratio": float(q.get("volume_ratio", 1.0) or 1.0),
                }

        now = datetime.now(UTC)

        for alert in alerts:
            symbol = alert.symbol
            if not symbol or symbol not in quote_map:
                continue

            condition_data = alert.condition or {}
            threshold = float(condition_data.get("value", 0))

            try:
                alert_type = AlertType(alert.alert_type)
            except ValueError:
                continue

            condition = AlertCondition(
                alert_id=str(alert.id),
                user_id=str(alert.user_id),
                symbol=symbol,
                alert_type=alert_type,
                threshold=threshold,
                label=alert.message or f"Alert on {symbol}",
                status=AlertStatus.PENDING,
            )

            event = evaluate_price_alert(condition, quote_map[symbol])
            if event is None:
                continue

            # Mark alert as triggered
            alert.triggered_at = now
            alert.is_active = False
            triggered_count += 1

            # Publish to Redis pub/sub for WebSocket delivery
            channel = CHANNEL_ALERTS.format(user_id=str(alert.user_id))
            payload = {
                "type": "alert_triggered",
                "alert_id": event.alert_id,
                "user_id": event.user_id,
                "symbol": event.symbol,
                "alert_type": event.alert_type,
                "threshold": event.threshold,
                "actual_value": event.actual_value,
                "label": event.label,
                "message": event.message,
                "triggered_at": event.triggered_at,
            }
            try:
                await publish(channel, payload)
            except Exception:  # noqa: BLE001
                logger.debug("tasks.evaluate_alerts.publish_error", alert_id=event.alert_id)

        if triggered_count > 0:
            await session.commit()
            logger.info(
                "tasks.evaluate_alerts.done",
                evaluated=evaluated_count,
                triggered=triggered_count,
            )

    return {
        "status": "ok",
        "evaluated": evaluated_count,
        "triggered": triggered_count,
    }
