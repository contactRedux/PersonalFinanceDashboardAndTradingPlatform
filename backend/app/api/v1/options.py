"""Options chain endpoints — full implementation in ST-9."""
from fastapi import APIRouter, Query

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/chain/{symbol}")
async def get_options_chain(symbol: str, expiry: str = Query(None), _: dict = CurrentUser):
    return {
        "symbol": symbol.upper(), "expiry": expiry,
        "chain": [], "note": "Options chain in ST-9",
    }


@router.get("/expirations/{symbol}")
async def get_expirations(symbol: str, _: dict = CurrentUser):
    return {"symbol": symbol.upper(), "expirations": []}


@router.get("/iv-surface/{symbol}")
async def get_iv_surface(symbol: str, _: dict = CurrentUser):
    return {"symbol": symbol.upper(), "surface": [], "note": "IV surface in ST-10"}


@router.get("/unusual-activity")
async def get_unusual_activity(symbol: str = Query(None), _: dict = CurrentUser):
    return {"activity": [], "note": "Unusual activity in ST-10"}
