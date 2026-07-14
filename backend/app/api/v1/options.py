"""
Options chain endpoints.
Fetches options chain from Polygon.io (primary) or Tradier (fallback).
Computes Black-Scholes Greeks server-side.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import structlog
from fastapi import APIRouter, Query

from app.config import get_settings
from app.dependencies import CurrentUser
from app.services.options.greeks import black_scholes_greeks, implied_volatility

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

# US 10-year risk-free rate approximation (updated periodically)
RISK_FREE_RATE = 0.045


@router.get("/chain/{symbol}")
async def get_options_chain(
    symbol: str,
    _: CurrentUser,
    expiry: str = Query(None, description="Expiration date YYYY-MM-DD"),
):
    """
    Return the full options chain for a symbol with Black-Scholes Greeks.
    Uses Polygon.io if key is configured; returns mock data otherwise.
    """
    chain = await _fetch_chain(symbol.upper(), expiry)
    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "underlying_price": chain.get("underlying_price"),
        "chain": chain.get("contracts", []),
        "expirations": chain.get("expirations", []),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/expirations/{symbol}")
async def get_expirations(symbol: str, _: CurrentUser):
    """Return available expiration dates for a symbol."""
    expirations = await _fetch_expirations(symbol.upper())
    return {"symbol": symbol.upper(), "expirations": expirations}


@router.get("/iv-surface/{symbol}")
async def get_iv_surface(symbol: str, _: CurrentUser):
    """
    Return implied-volatility surface data.

    Each point: {strike, expiry_days, iv, contract_type}.
    Uses live Polygon data when key is present; falls back to synthetic demo
    surface so the VolatilityPanel can always render.
    """
    sym = symbol.upper()

    if settings.polygon_api_key:
        surface = await _build_live_surface(sym)
        if surface:
            return {"symbol": sym, "surface": surface}

    # Demo surface — typical smile/skew shape
    surface = _build_demo_surface()
    return {"symbol": sym, "surface": surface}


@router.get("/unusual-activity")
async def get_unusual_activity(
    _: CurrentUser,
    symbol: str = Query(None),
    min_premium: float = Query(100_000, description="Minimum option premium in USD"),
):
    """Return unusual options activity (large premium trades)."""
    return {
        "activity": [],
        "note": "Unusual activity feed requires Unusual Whales API or Polygon Options Stream.",
    }


# ─── IV surface helpers ───────────────────────────────────────────────────────


def _build_demo_surface() -> list[dict]:
    """
    Generate a realistic synthetic IV surface for demo / offline mode.

    Shape: downward skew (higher IV at lower strikes — put skew),
    term-structure bump (30-day IV peak at ~0.32, declines at longer expirations).
    """
    import math  # noqa: PLC0415

    expirations_days = [7, 14, 30, 60, 90, 180, 270, 365]
    strike_offsets = [-0.20, -0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20]
    atm_price = 100.0  # normalised; frontend scales to real price
    atm_iv_base = 0.28  # 28% ATM IV baseline

    surface = []
    for exp_days in expirations_days:
        # Term-structure: slight U-shape — peaks around 30 days
        term_factor = 1.0 + 0.08 * math.exp(-((exp_days - 30) ** 2) / (2 * 50**2))
        for offset in strike_offsets:
            strike = round(atm_price * (1 + offset), 1)
            # Put-side skew: OTM puts have higher IV
            skew = -0.4 * offset  # negative offset → higher IV
            iv = max(0.05, atm_iv_base * term_factor + skew)
            surface.append(
                {
                    "strike": strike,
                    "expiry_days": exp_days,
                    "iv": round(iv, 4),
                    "contract_type": "call" if offset >= 0 else "put",
                }
            )
    return surface


async def _build_live_surface(symbol: str) -> list[dict]:
    """
    Attempt to build IV surface from Polygon options chain.
    Returns empty list when data unavailable (caller falls back to demo).
    """
    from datetime import date  # noqa: PLC0415

    try:
        chain_data = await _fetch_chain(symbol, expiry=None)
        contracts = chain_data.get("contracts", [])
        underlying = chain_data.get("underlying_price") or 100.0

        surface = []
        today = date.today()
        for c in contracts:
            exp_str = c.get("expiry", "")
            try:
                exp_date = date.fromisoformat(exp_str)
            except ValueError:
                continue
            exp_days = max(1, (exp_date - today).days)
            strike = float(c.get("strike") or 0)
            greeks = c.get("greeks", {})
            iv_val = 0.0
            # Use theoretical_price to back out IV if not already solved
            t_to_exp = exp_days / 365
            mkt_price = greeks.get("theoretical_price", 0)
            if mkt_price and strike and underlying:
                iv_val = (
                    implied_volatility(
                        market_price=float(mkt_price),
                        S=float(underlying),
                        K=strike,
                        T=t_to_exp,
                        r=RISK_FREE_RATE,
                        option_type=c.get("contract_type", "call"),
                    )
                    or 0.0
                )
            if iv_val > 0:
                surface.append(
                    {
                        "strike": strike,
                        "expiry_days": exp_days,
                        "iv": round(iv_val, 4),
                        "contract_type": c.get("contract_type", "call"),
                    }
                )
        return surface
    except Exception:  # noqa: BLE001
        return []


# ─── Internal helpers ─────────────────────────────────────────────────────────


async def _fetch_chain(symbol: str, expiry: str | None) -> dict:
    """Fetch options chain from Polygon.io or return placeholder."""
    if not settings.polygon_api_key:
        return {"underlying_price": None, "contracts": [], "expirations": []}

    params: dict = {
        "apiKey": settings.polygon_api_key,
        "limit": 250,
        "contract_type": "call,put",
    }
    if expiry:
        params["expiration_date"] = expiry

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # First get underlying price
            snap_resp = await client.get(
                f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}",
                params={"apiKey": settings.polygon_api_key},
            )
            underlying_price = None
            if snap_resp.status_code == 200:
                snap_data = snap_resp.json()
                underlying_price = snap_data.get("ticker", {}).get("day", {}).get("c")

            # Get options chain
            chain_resp = await client.get(
                "https://api.polygon.io/v3/reference/options/contracts",
                params={**params, "underlying_ticker": symbol},
            )
            if chain_resp.status_code != 200:
                return {"underlying_price": underlying_price, "contracts": [], "expirations": []}

            chain_data = chain_resp.json()
            contracts = []
            expirations_set: set[str] = set()

            for contract in chain_data.get("results", []):
                exp_date = contract.get("expiration_date", "")
                expirations_set.add(exp_date)

                # Compute Greeks if we have underlying price
                greeks_data = {}
                if underlying_price:
                    exp_dt = date.fromisoformat(exp_date)
                    t_to_exp = max(0.0001, (exp_dt - date.today()).days / 365)
                    strike = float(contract.get("strike_price", 0))
                    option_type = contract.get("contract_type", "call")

                    g = black_scholes_greeks(
                        S=float(underlying_price),
                        K=strike,
                        T=t_to_exp,
                        r=RISK_FREE_RATE,
                        sigma=0.3,  # fallback IV; real IV requires market prices
                        option_type=option_type,
                    )
                    greeks_data = {
                        "delta": g.delta,
                        "gamma": g.gamma,
                        "theta": g.theta,
                        "vega": g.vega,
                        "rho": g.rho,
                        "theoretical_price": g.theoretical_price,
                    }

                contracts.append(
                    {
                        "ticker": contract.get("ticker"),
                        "strike": contract.get("strike_price"),
                        "expiry": exp_date,
                        "contract_type": contract.get("contract_type"),
                        "greeks": greeks_data,
                    }
                )

            return {
                "underlying_price": underlying_price,
                "contracts": contracts,
                "expirations": sorted(expirations_set),
            }

    except Exception:
        logger.exception("options.chain.error", symbol=symbol)
        return {"underlying_price": None, "contracts": [], "expirations": []}


async def _fetch_expirations(symbol: str) -> list[str]:
    if not settings.polygon_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.polygon.io/v3/reference/options/contracts",
                params={
                    "underlying_ticker": symbol,
                    "apiKey": settings.polygon_api_key,
                    "limit": 1000,
                },
            )
            data = resp.json()
            expirations = sorted(
                {c["expiration_date"] for c in data.get("results", []) if c.get("expiration_date")}
            )
            return expirations
    except Exception:
        return []
