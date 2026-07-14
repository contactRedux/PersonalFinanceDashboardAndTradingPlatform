"""
Macro / FRED endpoints — full implementation.

GET /macro/indicators   — current values for all key macro indicators
GET /macro/yield-curve  — current US Treasury yield curve
GET /macro/fred/{id}    — arbitrary FRED series historical data
GET /macro/vix          — latest VIX and market volatility context
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog
from fastapi import APIRouter, Query

from app.config import get_settings
from app.dependencies import CurrentUser
from app.services.macro.fred import (
    build_demo_macro_snapshot,
    build_demo_yield_curve,
    fetch_macro_snapshot,
    fetch_series_history,
    fetch_yield_curve,
)

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

POLYGON_VIX_SYMBOL = "I:VIX"


@router.get("/indicators")
async def get_macro_indicators(_: CurrentUser):
    """
    Return current values for all key macro indicators from FRED.
    Falls back to demo data if FRED API key not configured.
    """
    if settings.fred_api_key:
        data = await fetch_macro_snapshot()
        data["as_of"] = datetime.now(UTC).isoformat()
        return data
    return build_demo_macro_snapshot()


@router.get("/yield-curve")
async def get_yield_curve(_: CurrentUser):
    """
    Return the current US Treasury yield curve (1M through 30Y).
    Falls back to demo data if FRED API key not configured.
    """
    if settings.fred_api_key:
        curve = await fetch_yield_curve()
        if curve:
            return {
                "curve": curve,
                "inverted": _is_inverted(curve),
                "as_of": datetime.now(UTC).isoformat(),
            }
    demo = build_demo_yield_curve()
    return {
        "curve": demo,
        "inverted": _is_inverted(demo),
        "as_of": datetime.now(UTC).isoformat(),
        "note": "Demo data — configure FRED_API_KEY for live yield curve.",
    }


@router.get("/fred/{series_id}")
async def get_fred_series(
    series_id: str,
    _: CurrentUser,
    start: str = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Fetch arbitrary FRED time series historical data.
    Series IDs: DFF, CPIAUCSL, UNRATE, GDP, T10Y2Y, etc.
    """
    if not settings.fred_api_key:
        return {
            "series_id": series_id,
            "data": [],
            "note": "Configure FRED_API_KEY for live data.",
        }
    data = await fetch_series_history(series_id.upper(), observation_start=start, limit=limit)
    return {"series_id": series_id.upper(), "data": data, "count": len(data)}


@router.get("/vix")
async def get_vix(_: CurrentUser):
    """
    Return current VIX level with regime classification.
    Uses Polygon.io snapshot if key configured; otherwise demo data.
    """
    vix_value: float | None = None

    if settings.polygon_api_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://api.polygon.io/v2/snapshot/locale/us/markets/indices/tickers/{POLYGON_VIX_SYMBOL}",
                    params={"apiKey": settings.polygon_api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    vix_value = data.get("results", {}).get("value")
        except Exception:  # noqa: BLE001
            logger.debug("vix.fetch_error")

    if vix_value is None:
        vix_value = 18.42  # demo

    regime = _vix_regime(vix_value)
    return {
        "value": vix_value,
        "regime": regime,
        "as_of": datetime.now(UTC).isoformat(),
    }


def _is_inverted(curve: list[dict]) -> bool:
    """Check if yield curve is inverted (10Y < 2Y)."""
    yields = {p["maturity"]: p["yield"] for p in curve}
    y10 = yields.get("10Y")
    y2 = yields.get("2Y")
    if y10 is not None and y2 is not None:
        return y10 < y2
    return False


def _vix_regime(vix: float) -> str:
    if vix < 15:
        return "low_volatility"
    if vix < 20:
        return "normal"
    if vix < 30:
        return "elevated"
    if vix < 40:
        return "high_volatility"
    return "extreme_fear"
