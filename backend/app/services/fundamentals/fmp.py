"""
Financial Modeling Prep (FMP) adapter.

All endpoints target the free-tier base URL (v3). When upgrading to a paid
tier, no code changes are needed — swap the API key and the higher quota
applies automatically.

Free-tier limits: 250 requests / day.
All responses are Redis-cached (TTL 4 h for fundamentals, 1 h for real-time
endpoints) to stay well within the daily quota.

Endpoints used:
  /profile/{symbol}               — company overview, sector, beta, etc.
  /income-statement/{symbol}      — annual + quarterly P&L
  /balance-sheet-statement/{symbol} — annual + quarterly balance sheet
  /cash-flow-statement/{symbol}   — annual + quarterly cash flow
  /key-metrics/{symbol}           — EV/EBITDA, ROE, FCF yield, etc.
  /discounted-cash-flow/{symbol}  — DCF intrinsic value estimate
  /historical/earning_calendar    — per-symbol earnings history + EPS actual/est
  /analyst-estimates/{symbol}     — forward EPS/revenue consensus estimates
  /insider-trading                — insider buy/sell Form 4 filings
  /institutional-ownership/{symbol} — top 13-F institutional holders
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

FMP_BASE = "https://financialmodelingprep.com/api/v3"
_CACHE_TTL_FUNDAMENTALS = 60 * 60 * 4   # 4 hours
_CACHE_TTL_REALTIME = 60 * 60            # 1 hour


# ─── Redis cache helpers ──────────────────────────────────────────────────────

async def _cache_get(key: str) -> str | None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        return await redis.get(key)
    except Exception:  # noqa: BLE001
        return None


async def _cache_set(key: str, value: str, ttl: int) -> None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        await redis.setex(key, ttl, value)
    except Exception:  # noqa: BLE001
        pass


# ─── Internal HTTP helper ─────────────────────────────────────────────────────

async def _get(path: str, params: dict | None = None, cache_key: str | None = None, cache_ttl: int = _CACHE_TTL_FUNDAMENTALS) -> dict | list | None:
    """
    GET a FMP endpoint. Returns parsed JSON or None on error.
    Caches result in Redis when cache_key is provided.
    Returns empty list [] (not None) on 200 with empty body.
    """
    if not settings.fmp_api_key:
        return None

    if cache_key:
        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, json.JSONDecodeError):
                pass

    merged_params = {"apikey": settings.fmp_api_key, **(params or {})}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{FMP_BASE}{path}", params=merged_params)
            if resp.status_code != 200:
                logger.debug("fmp.http_error", path=path, status=resp.status_code)
                return None
            data = resp.json()
            if cache_key:
                await _cache_set(cache_key, json.dumps(data), cache_ttl)
            return data
    except Exception:  # noqa: BLE001
        logger.debug("fmp.request_error", path=path)
        return None


# ─── Public adapter methods ───────────────────────────────────────────────────

async def get_profile(symbol: str) -> dict | None:
    """
    Company profile: name, sector, industry, description, CEO, employees,
    exchange, market cap, beta, dividend yield, 52-week high/low.
    """
    data = await _get(
        f"/profile/{symbol.upper()}",
        cache_key=f"fmp:profile:{symbol.upper()}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    if isinstance(data, list) and data:
        return data[0]
    return None


async def get_income_statement(symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
    """
    Income statement (annual or quarterly).
    period: "annual" | "quarter"
    """
    data = await _get(
        f"/income-statement/{symbol.upper()}",
        params={"period": period, "limit": limit},
        cache_key=f"fmp:income:{symbol.upper()}:{period}:{limit}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    return data if isinstance(data, list) else []


async def get_balance_sheet(symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
    """
    Balance sheet statement (annual or quarterly).
    """
    data = await _get(
        f"/balance-sheet-statement/{symbol.upper()}",
        params={"period": period, "limit": limit},
        cache_key=f"fmp:balance:{symbol.upper()}:{period}:{limit}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    return data if isinstance(data, list) else []


async def get_cash_flow(symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
    """
    Cash flow statement (annual or quarterly).
    """
    data = await _get(
        f"/cash-flow-statement/{symbol.upper()}",
        params={"period": period, "limit": limit},
        cache_key=f"fmp:cashflow:{symbol.upper()}:{period}:{limit}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    return data if isinstance(data, list) else []


async def get_key_metrics(symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
    """
    Key financial metrics: EV/EBITDA, FCF yield, ROE, ROIC, etc.
    """
    data = await _get(
        f"/key-metrics/{symbol.upper()}",
        params={"period": period, "limit": limit},
        cache_key=f"fmp:metrics:{symbol.upper()}:{period}:{limit}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    return data if isinstance(data, list) else []


async def get_dcf(symbol: str) -> dict | None:
    """
    Discounted cash flow (DCF) intrinsic value estimate.
    Returns: {"symbol": ..., "date": ..., "dcf": float, "Stock Price": float}
    """
    data = await _get(
        f"/discounted-cash-flow/{symbol.upper()}",
        cache_key=f"fmp:dcf:{symbol.upper()}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data:
        return data[0]
    return None


async def get_earnings_history(symbol: str, limit: int = 10) -> list[dict]:
    """
    Historical earnings: EPS actual vs estimate, surprise %, report date.
    """
    data = await _get(
        "/historical/earning_calendar",
        params={"symbol": symbol.upper(), "limit": limit},
        cache_key=f"fmp:earnings:{symbol.upper()}:{limit}",
        cache_ttl=_CACHE_TTL_REALTIME,
    )
    return data if isinstance(data, list) else []


async def get_analyst_estimates(symbol: str, limit: int = 4) -> list[dict]:
    """
    Analyst forward EPS and revenue consensus estimates.
    """
    data = await _get(
        f"/analyst-estimates/{symbol.upper()}",
        params={"limit": limit},
        cache_key=f"fmp:estimates:{symbol.upper()}:{limit}",
        cache_ttl=_CACHE_TTL_REALTIME,
    )
    return data if isinstance(data, list) else []


async def get_insider_transactions(symbol: str, limit: int = 20) -> list[dict]:
    """
    Recent insider buy/sell transactions (Form 4 SEC filings).
    Returns list sorted newest-first.
    """
    data = await _get(
        "/insider-trading",
        params={"symbol": symbol.upper(), "limit": limit},
        cache_key=f"fmp:insider:{symbol.upper()}:{limit}",
        cache_ttl=_CACHE_TTL_REALTIME,
    )
    return data if isinstance(data, list) else []


async def get_institutional_holders(symbol: str, limit: int = 10) -> list[dict]:
    """
    Top institutional holders from 13-F filings.
    """
    data = await _get(
        f"/institutional-ownership/{symbol.upper()}",
        cache_key=f"fmp:institutions:{symbol.upper()}:{limit}",
        cache_ttl=_CACHE_TTL_FUNDAMENTALS,
    )
    if isinstance(data, list):
        return data[:limit]
    return []


async def build_fundamentals_payload(symbol: str) -> dict:
    """
    Build the complete fundamentals payload for a symbol.
    Fetches all endpoints in parallel and merges results.
    Returns a dict suitable for the /fundamentals/{symbol} endpoint.
    Gracefully handles partial failures — missing sections are empty.
    """
    import asyncio  # noqa: PLC0415

    sym = symbol.upper()

    (
        profile,
        income,
        balance,
        cashflow,
        metrics,
        dcf,
        earnings,
        estimates,
        insiders,
        institutions,
    ) = await asyncio.gather(
        get_profile(sym),
        get_income_statement(sym),
        get_balance_sheet(sym),
        get_cash_flow(sym),
        get_key_metrics(sym),
        get_dcf(sym),
        get_earnings_history(sym),
        get_analyst_estimates(sym),
        get_insider_transactions(sym),
        get_institutional_holders(sym),
    )

    return {
        "symbol": sym,
        "as_of": datetime.now(UTC).isoformat(),
        "profile": profile,
        "income_statement": income,
        "balance_sheet": balance,
        "cash_flow": cashflow,
        "key_metrics": metrics,
        "dcf": dcf,
        "earnings_history": earnings,
        "analyst_estimates": estimates,
        "insider_transactions": insiders,
        "institutional_holders": institutions,
    }


def build_demo_fundamentals(symbol: str) -> dict:
    """Demo payload returned when FMP_API_KEY is not configured."""
    return {
        "symbol": symbol.upper(),
        "as_of": datetime.now(UTC).isoformat(),
        "note": "Demo data — configure FMP_API_KEY for live fundamentals.",
        "profile": {
            "companyName": f"{symbol.upper()} Inc.",
            "sector": "Technology",
            "industry": "Software—Application",
            "description": "Demo company description.",
            "mktCap": 3_000_000_000_000,
            "beta": 1.25,
            "dividendYield": 0.005,
            "dcfDiff": 12.5,
        },
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "key_metrics": [],
        "dcf": {"dcf": 195.0, "Stock Price": 182.0},
        "earnings_history": [],
        "analyst_estimates": [],
        "insider_transactions": [],
        "institutional_holders": [],
    }
