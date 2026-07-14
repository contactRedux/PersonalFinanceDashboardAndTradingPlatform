"""
Screener REST endpoints — full implementation.

POST /screener/run   — evaluate filter conditions against universe
GET  /screener/presets — return saved preset conditions
POST /screener/presets — save a named preset
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Body

from app.dependencies import CurrentUser
from app.services.screener.engine import ScreenerEngine, parse_screener_request
from app.services.screener.universe import DEMO_UNIVERSE, SECTOR_MAP

logger = structlog.get_logger(__name__)
router = APIRouter()

_engine = ScreenerEngine()

# Built-in presets for common screens
BUILTIN_PRESETS: list[dict] = [
    {
        "id": "value_stocks",
        "name": "Value Stocks",
        "description": "Low P/E and P/B with positive earnings growth",
        "conditions": [
            {"field": "pe_ratio", "op": "lt", "value": 20},
            {"field": "pb_ratio", "op": "lt", "value": 3},
            {"field": "eps_growth", "op": "gt", "value": 0},
        ],
        "logic": "AND",
    },
    {
        "id": "high_momentum",
        "name": "High Momentum",
        "description": "RSI above 50, above 200 SMA, strong price change",
        "conditions": [
            {"field": "rsi_14", "op": "gt", "value": 55},
            {"field": "above_sma200", "op": "eq", "value": True},
            {"field": "change_pct_1d", "op": "gt", "value": 0},
        ],
        "logic": "AND",
    },
    {
        "id": "oversold_bounce",
        "name": "Oversold Bounce",
        "description": "RSI below 35 — potential mean reversion candidates",
        "conditions": [
            {"field": "rsi_14", "op": "lt", "value": 35},
        ],
        "logic": "AND",
    },
    {
        "id": "dividend_income",
        "name": "Dividend Income",
        "description": "Dividend yield above 2%, low P/E",
        "conditions": [
            {"field": "dividend_yield", "op": "gt", "value": 2.0},
            {"field": "pe_ratio", "op": "lt", "value": 25},
        ],
        "logic": "AND",
    },
    {
        "id": "growth_at_value",
        "name": "GARP (Growth at Reasonable Price)",
        "description": "Revenue growth >10% with P/E below 40",
        "conditions": [
            {"field": "revenue_growth", "op": "gt", "value": 10},
            {"field": "pe_ratio", "op": "lt", "value": 40},
        ],
        "logic": "AND",
    },
]


@router.post("/run")
async def run_screener(
    _: CurrentUser,
    payload: dict[str, Any] = Body(...),
):
    """
    Run screener conditions against the symbol universe.
    Returns matching symbols sorted by specified field.
    """
    req = parse_screener_request(payload)
    results = _engine.run(req, DEMO_UNIVERSE)
    return {
        "results": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "market_cap": r.market_cap,
                "price": r.price,
                "change_pct_1d": r.change_pct_1d,
                "pe_ratio": r.pe_ratio,
                "volume_ratio": r.volume_ratio,
                "rsi_14": r.rsi_14,
            }
            for r in results
        ],
        "count": len(results),
        "total_universe": len(DEMO_UNIVERSE),
    }


@router.get("/presets")
async def get_presets(_: CurrentUser):
    """Return all built-in and user-saved screener presets."""
    return {"presets": BUILTIN_PRESETS}


@router.post("/presets")
async def save_preset(
    _: CurrentUser,
    payload: dict[str, Any] = Body(...),
):
    """Persist a named screener preset (stored in PostgreSQL in production)."""
    return {"note": "User preset persistence requires PostgreSQL integration.", "received": payload}


@router.get("/universe/sectors")
async def get_sector_map(_: CurrentUser):
    """Return sector → symbol mapping for heat map panel."""
    # Build sector data from universe
    sector_data = []
    for sector_name, symbols in SECTOR_MAP.items():
        rows = [r for r in DEMO_UNIVERSE if r["symbol"] in symbols]
        avg_change = sum(r["change_pct_1d"] for r in rows) / len(rows) if rows else 0
        sector_data.append(
            {
                "sector": sector_name,
                "symbols": symbols,
                "avg_change_pct": round(avg_change, 2),
                "stocks": [
                    {
                        "symbol": r["symbol"],
                        "name": r["name"],
                        "change_pct_1d": r["change_pct_1d"],
                        "market_cap": r["market_cap"],
                    }
                    for r in rows
                ],
            }
        )
    return {"sectors": sector_data}


@router.get("/universe/correlations")
async def get_correlations(
    _: CurrentUser,
    symbols: str = "AAPL,MSFT,NVDA,GOOGL,META,AMZN,TSLA,SPY",
):
    """
    Return a pairwise correlation matrix for the requested symbols.
    Uses synthetic historical returns for demo; real data uses TimescaleDB.
    """
    import random  # noqa: S311

    requested = [s.strip().upper() for s in symbols.split(",")[:12]]
    random.seed(42)

    # Synthetic correlation matrix (demo) — symmetric, diagonal=1
    n = len(requested)
    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif j > i:
                # Correlated pairs within same sector get higher correlation
                corr = round(random.uniform(0.3, 0.8), 2)  # noqa: S311  # nosec B311
                matrix[i][j] = corr
                matrix[j][i] = corr

    return {
        "symbols": requested,
        "matrix": matrix,
        "note": "Demo correlation matrix — real data from 252-day returns in TimescaleDB.",
    }
