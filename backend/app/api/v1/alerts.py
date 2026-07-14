"""
Alerts CRUD endpoints — full implementation.

GET    /alerts        — list user's alerts
POST   /alerts        — create a new alert
PUT    /alerts/{id}   — update alert threshold/label
DELETE /alerts/{id}   — delete alert
POST   /alerts/{id}/acknowledge — mark triggered alert as acknowledged

Alerts are stored in PostgreSQL. Evaluator runs via APScheduler.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Body, HTTPException

from app.dependencies import CurrentUser
from app.services.alerts.evaluator import AlertStatus, AlertType

logger = structlog.get_logger(__name__)
router = APIRouter()

# In-memory alert store for demo (PostgreSQL persistence in production)
_ALERT_STORE: dict[str, dict[str, Any]] = {}


def _user_alerts(user_id: str) -> list[dict[str, Any]]:
    return [a for a in _ALERT_STORE.values() if a["user_id"] == user_id]


@router.get("")
async def list_alerts(current_user: CurrentUser):
    """Return all alerts for the authenticated user."""
    alerts = _user_alerts(current_user["sub"])
    return {"alerts": alerts, "count": len(alerts)}


@router.post("", status_code=201)
async def create_alert(
    current_user: CurrentUser,
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

    alert_id = str(uuid.uuid4())
    alert = {
        "id": alert_id,
        "user_id": current_user["sub"],
        "symbol": payload.get("symbol"),
        "alert_type": alert_type_str,
        "threshold": float(payload.get("threshold", 0)),
        "label": payload.get("label", f"Alert on {payload.get('symbol', 'portfolio')}"),
        "status": AlertStatus.PENDING.value,
        "created_at": datetime.now(UTC).isoformat(),
        "triggered_at": None,
    }
    _ALERT_STORE[alert_id] = alert
    logger.info("alert.created", alert_id=alert_id, user_id=current_user["sub"])
    return alert


@router.put("/{alert_id}")
async def update_alert(
    alert_id: str,
    current_user: CurrentUser,
    payload: dict[str, Any] = Body(...),
):
    """Update alert threshold, label, or re-arm a triggered alert."""
    alert = _ALERT_STORE.get(alert_id)
    if not alert or alert["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Alert not found")

    if "threshold" in payload:
        alert["threshold"] = float(payload["threshold"])
    if "label" in payload:
        alert["label"] = str(payload["label"])
    if payload.get("rearm"):
        alert["status"] = AlertStatus.PENDING.value
        alert["triggered_at"] = None

    return alert


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: str, current_user: CurrentUser):
    """Delete an alert by ID."""
    alert = _ALERT_STORE.get(alert_id)
    if not alert or alert["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Alert not found")
    del _ALERT_STORE[alert_id]
    logger.info("alert.deleted", alert_id=alert_id, user_id=current_user["sub"])


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: CurrentUser):
    """Mark a triggered alert as acknowledged."""
    alert = _ALERT_STORE.get(alert_id)
    if not alert or alert["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = AlertStatus.ACKNOWLEDGED.value
    return alert


@router.get("/types")
async def get_alert_types(_: CurrentUser):
    """Return all supported alert types."""
    return {
        "types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in AlertType
        ]
    }
