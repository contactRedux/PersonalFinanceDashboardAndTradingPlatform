"""Alerts CRUD + trigger evaluation — full implementation in ST-10."""
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("")
async def list_alerts(_: CurrentUser):
    return {"alerts": [], "note": "Alerts in ST-10"}


@router.post("")
async def create_alert(_: CurrentUser):
    return {"note": "Alert creation in ST-10"}


@router.put("/{alert_id}")
async def update_alert(alert_id: str, _: CurrentUser):
    return {"note": f"Update alert {alert_id} in ST-10"}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, _: CurrentUser):
    return {"note": f"Delete alert {alert_id} in ST-10"}
