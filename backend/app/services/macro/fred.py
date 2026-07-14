"""
FRED (Federal Reserve Economic Data) integration.

Fetches macro economic time series data from the FRED API.
Key series IDs:
  - DFF   : Fed Funds Effective Rate
  - T10Y2Y: 10Y-2Y Treasury Spread (yield curve slope)
  - T10YIE: 10-Year Breakeven Inflation Rate
  - CPIAUCSL: CPI
  - GDP   : Gross Domestic Product
  - UNRATE: Unemployment Rate
  - VIXCLS: CBOE VIX
  - DTWEXBGS: US Dollar Index (DXY proxy)
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

FRED_BASE = "https://api.stlouisfed.org/fred"

# Canonical macro indicator definitions
MACRO_SERIES: dict[str, dict] = {
    "fed_funds_rate": {"id": "DFF",      "label": "Fed Funds Rate",         "unit": "%"},
    "cpi":            {"id": "CPIAUCSL", "label": "CPI (YoY)",              "unit": "Index"},
    "gdp":            {"id": "GDP",      "label": "GDP",                     "unit": "$B"},
    "unemployment":   {"id": "UNRATE",   "label": "Unemployment Rate",       "unit": "%"},
    "yield_spread":   {"id": "T10Y2Y",   "label": "10Y-2Y Spread",          "unit": "%"},
    "breakeven_inf":  {"id": "T10YIE",   "label": "10Y Breakeven Inflation", "unit": "%"},
    "dxy":            {"id": "DTWEXBGS", "label": "US Dollar Index",         "unit": "Index"},
}

# Treasury yield series for yield curve
YIELD_CURVE_SERIES: dict[str, str] = {
    "1M":  "DGS1MO",
    "3M":  "DGS3MO",
    "6M":  "DGS6MO",
    "1Y":  "DGS1",
    "2Y":  "DGS2",
    "3Y":  "DGS3",
    "5Y":  "DGS5",
    "7Y":  "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}


async def fetch_series_latest(series_id: str) -> float | None:
    """Fetch the most recent observation for a FRED series."""
    if not settings.fred_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{FRED_BASE}/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
            )
            if resp.status_code != 200:
                return None
            obs = resp.json().get("observations", [])
            if obs and obs[0].get("value") not in (".", ""):
                return float(obs[0]["value"])
    except Exception:  # noqa: BLE001
        logger.debug("fred.fetch_latest_error", series_id=series_id)
    return None


async def fetch_series_history(
    series_id: str,
    observation_start: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Fetch time series observations from FRED.
    Returns: [{"date": "YYYY-MM-DD", "value": float}, ...]
    """
    if not settings.fred_api_key:
        return []
    if observation_start is None:
        start = (date.today() - timedelta(days=365 * 2)).isoformat()
    else:
        start = observation_start

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{FRED_BASE}/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "observation_start": start,
                    "sort_order": "asc",
                    "limit": limit,
                },
            )
            if resp.status_code != 200:
                return []
            return [
                {"date": o["date"], "value": float(o["value"])}
                for o in resp.json().get("observations", [])
                if o.get("value") not in (".", "")
            ]
    except Exception:  # noqa: BLE001
        logger.debug("fred.fetch_history_error", series_id=series_id)
    return []


async def fetch_macro_snapshot() -> dict:
    """
    Fetch all key macro indicators in parallel.
    Returns a dict keyed by canonical name.
    """
    import asyncio

    tasks = {
        key: asyncio.create_task(fetch_series_latest(meta["id"]))
        for key, meta in MACRO_SERIES.items()
    }
    results = {}
    for key, task in tasks.items():
        val = await task
        results[key] = {
            "value": val,
            "label": MACRO_SERIES[key]["label"],
            "unit": MACRO_SERIES[key]["unit"],
        }
    return results


async def fetch_yield_curve() -> list[dict]:
    """
    Fetch current yields for all treasury maturities.
    Returns: [{"maturity": "10Y", "yield": 4.32}, ...]
    """
    import asyncio

    tasks = {
        maturity: asyncio.create_task(fetch_series_latest(series_id))
        for maturity, series_id in YIELD_CURVE_SERIES.items()
    }
    curve = []
    for maturity, task in tasks.items():
        val = await task
        if val is not None:
            curve.append({"maturity": maturity, "yield": val})

    # Sort by maturity duration
    order = list(YIELD_CURVE_SERIES.keys())
    curve.sort(key=lambda x: order.index(x["maturity"]) if x["maturity"] in order else 99)
    return curve


def build_demo_yield_curve() -> list[dict]:
    """Return a realistic demo yield curve (used when FRED key not configured)."""
    return [
        {"maturity": "1M",  "yield": 5.32},
        {"maturity": "3M",  "yield": 5.35},
        {"maturity": "6M",  "yield": 5.25},
        {"maturity": "1Y",  "yield": 5.01},
        {"maturity": "2Y",  "yield": 4.64},
        {"maturity": "3Y",  "yield": 4.42},
        {"maturity": "5Y",  "yield": 4.28},
        {"maturity": "7Y",  "yield": 4.30},
        {"maturity": "10Y", "yield": 4.32},
        {"maturity": "20Y", "yield": 4.55},
        {"maturity": "30Y", "yield": 4.48},
    ]


def build_demo_macro_snapshot() -> dict:
    """Return demo macro data for UI development when FRED key not configured."""
    return {
        "fed_funds_rate": {"value": 5.33,  "label": "Fed Funds Rate",         "unit": "%"},
        "cpi":            {"value": 314.2, "label": "CPI (YoY)",              "unit": "Index"},
        "gdp":            {"value": 27350, "label": "GDP",                     "unit": "$B"},
        "unemployment":   {"value": 4.1,   "label": "Unemployment Rate",       "unit": "%"},
        "yield_spread":   {"value": -0.32, "label": "10Y-2Y Spread",          "unit": "%"},
        "breakeven_inf":  {"value": 2.31,  "label": "10Y Breakeven Inflation", "unit": "%"},
        "dxy":            {"value": 104.7, "label": "US Dollar Index",         "unit": "Index"},
        "as_of": datetime.now(UTC).isoformat(),
    }
