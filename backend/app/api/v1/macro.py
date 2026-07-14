"""Macro / FRED endpoints — full implementation in ST-10."""
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/indicators")
async def get_macro_indicators(_: CurrentUser):
    return {
        "vix": None, "dxy": None, "move": None,
        "fed_funds_rate": None, "note": "Macro in ST-10",
    }


@router.get("/yield-curve")
async def get_yield_curve(_: CurrentUser):
    return {"curve": [], "note": "Yield curve in ST-10"}


@router.get("/fred/{series_id}")
async def get_fred_series(series_id: str, _: CurrentUser):
    return {"series_id": series_id, "data": [], "note": "FRED in ST-10"}
