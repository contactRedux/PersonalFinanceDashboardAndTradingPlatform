"""Economic calendar endpoints — full implementation in ST-10."""
from fastapi import APIRouter, Query

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/events")
async def get_calendar_events(
    start: str = Query(None),
    end: str = Query(None),
    impact: str = Query(None, description="high|medium|low"),
    _: dict = CurrentUser,
):
    return {"events": [], "note": "Economic calendar in ST-10"}
