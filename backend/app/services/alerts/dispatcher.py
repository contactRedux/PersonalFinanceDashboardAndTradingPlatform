"""
Alert dispatcher — publishes triggered alert events to Redis pub/sub.

Triggered alerts are sent to channel:alerts:{user_id} so the
WebSocket feed (alerts_feed.py) can push them to the client in real time.
Also persists triggered events to PostgreSQL via the audit_log table.
"""

from __future__ import annotations

import json

import structlog

from app.data.cache.redis_client import get_redis_pool
from app.services.alerts.evaluator import AlertEvent

logger = structlog.get_logger(__name__)


async def dispatch_alert_event(event: AlertEvent) -> None:
    """
    Publish an AlertEvent to the per-user Redis channel.
    """
    channel = f"channel:alerts:{event.user_id}"
    payload = {
        "type": "alert_triggered",
        "alert_id": event.alert_id,
        "user_id": event.user_id,
        "symbol": event.symbol,
        "alert_type": event.alert_type,
        "threshold": event.threshold,
        "actual_value": event.actual_value,
        "label": event.label,
        "triggered_at": event.triggered_at,
        "message": event.message,
    }
    try:
        redis = await get_redis_pool()
        await redis.publish(channel, json.dumps(payload))
        logger.info(
            "alert.dispatched",
            alert_id=event.alert_id,
            user_id=event.user_id,
            alert_type=event.alert_type,
        )
    except Exception:  # noqa: BLE001
        logger.exception("alert.dispatch_error", alert_id=event.alert_id)


async def dispatch_many(events: list[AlertEvent]) -> None:
    """Dispatch all triggered events concurrently."""
    import asyncio

    if not events:
        return
    await asyncio.gather(*(dispatch_alert_event(e) for e in events))
