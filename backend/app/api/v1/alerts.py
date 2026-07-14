"""
Alerts CRUD endpoints — DB-backed implementation.

GET    /alerts               — list user's alerts
POST   /alerts               — create a new alert
PUT    /alerts/{id}          — update alert threshold/label or re-arm
DELETE /alerts/{id}          — delete alert
POST   /alerts/{id}/acknowledge — mark triggered alert as acknowledged
GET    /alerts/types         — list supported alert types
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Body, HTTPException
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models.alert import Alert
from app.services.alerts.evaluator import AlertStatus, AlertType

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _derive_status(row: Alert) -> str:
    """Derive the status string from ORM fields."""
    if hasattr(row, "acknowledged_at") and row.acknowledged_at is not None:
        return AlertStatus.ACKNOWLEDGED.value
    if row.triggered_at is not None:
        return AlertStatus.TRIGGERED.value
    if not row.is_active:
        return AlertStatus.EXPIRED.value
    return AlertStatus.PENDING.value


def _row_to_dict(row: Alert) -> dict[str, Any]:
    condition = row.condition or {}
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "symbol": row.symbol,
        "alert_type": row.alert_type,
        "threshold": condition.get("value", 0.0),
        "label": row.message or f"Alert on {row.symbol}",
        "status": _derive_status(row),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
    }


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


async def _get_owned_alert(alert_id: str, user_sub: str, db: Any) -> Alert:
    aid = _parse_uuid(alert_id)
    if aid is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    result = await db.execute(select(Alert).where(Alert.id == aid))
    row = result.scalar_one_or_none()
    if row is None or str(row.user_id) != user_sub:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("/types")
async def get_alert_types(_: CurrentUser):
    """Return all supported alert types."""
    return {
        "types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()} for t in AlertType
        ]
    }


@router.get("")
async def list_alerts(current_user: CurrentUser, db: DBSession):
    """Return all alerts for the authenticated user."""
    user_uuid = _parse_uuid(current_user["sub"])
    if user_uuid is None:
        return {"alerts": [], "count": 0}

    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == user_uuid)
        .order_by(Alert.created_at.desc())
    )
    rows = result.scalars().all()
    alerts = [_row_to_dict(r) for r in rows]
    return {"alerts": alerts, "count": len(alerts)}


@router.post("", status_code=201)
async def create_alert(
    current_user: CurrentUser,
    db: DBSession,
    payload: dict[str, Any] = Body(...),
):
    """
    Create a new alert.
    Required fields: symbol (optional), alert_type, threshold, label
    """
    alert_type_str = payload.get("alert_type", "")
    if alert_type_str not in {t.value for t in AlertType}:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid alert_type. Must be one of: {[t.value for t in AlertType]}",
        )

    user_uuid = _parse_uuid(current_user["sub"])
    if user_uuid is None:
        user_uuid = uuid.uuid4()

    threshold = float(payload.get("threshold", 0))
    symbol = payload.get("symbol") or "PORTFOLIO"
    label = payload.get("label") or f"Alert on {symbol}"

    row = Alert(
        user_id=user_uuid,
        symbol=symbol,
        alert_type=alert_type_str,
        condition={"field": "price", "op": "gte", "value": threshold},
        message=label,
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("alert.created", alert_id=str(row.id), user_id=str(user_uuid))
    return _row_to_dict(row)


@router.put("/{alert_id}")
async def update_alert(
    alert_id: str,
    current_user: CurrentUser,
    db: DBSession,
    payload: dict[str, Any] = Body(...),
):
    """Update alert threshold, label, or re-arm a triggered alert."""
    row = await _get_owned_alert(alert_id, current_user["sub"], db)

    if "threshold" in payload:
        condition = dict(row.condition or {})
        condition["value"] = float(payload["threshold"])
        row.condition = condition

    if "label" in payload:
        row.message = str(payload["label"])

    if payload.get("rearm"):
        row.triggered_at = None
        row.is_active = True
        if hasattr(row, "acknowledged_at"):
            row.acknowledged_at = None  # type: ignore[assignment]

    await db.commit()
    await db.refresh(row)
    return _row_to_dict(row)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str, current_user: CurrentUser, db: DBSession):
    """Delete an alert by ID."""
    row = await _get_owned_alert(alert_id, current_user["sub"], db)
    await db.delete(row)
    await db.commit()
    logger.info("alert.deleted", alert_id=alert_id, user_id=current_user["sub"])


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: CurrentUser, db: DBSession):
    """Mark a triggered alert as acknowledged."""
    row = await _get_owned_alert(alert_id, current_user["sub"], db)
    now = datetime.now(UTC)
    if hasattr(row, "acknowledged_at"):
        row.acknowledged_at = now  # type: ignore[assignment]
    await db.commit()
    await db.refresh(row)
    return _row_to_dict(row)
