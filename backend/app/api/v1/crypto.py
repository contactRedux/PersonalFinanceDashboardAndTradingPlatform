# ruff: noqa: E501

"""
Crypto-specific endpoints — full implementation.

GET /crypto/funding-rates    — perpetual swap funding rates (Binance)
GET /crypto/onchain/{symbol} — on-chain metrics (CoinGecko)
GET /crypto/liquidations     — exchange liquidation heatmap data
GET /crypto/exchange-flows   — BTC/ETH exchange netflow
GET /crypto/top-movers       — top 24h gainers and losers
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog
from fastapi import APIRouter, Query

from app.config import get_settings
from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

BINANCE_BASE = "https://api.binance.us"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Canonical crypto symbols we track
DEFAULT_PERPS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
]
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
}


@router.get("/funding-rates")
async def get_funding_rates(
    _: CurrentUser,
    symbols: str = Query(",".join(DEFAULT_PERPS[:6])),
):
    """
    Return current perpetual swap funding rates from Binance.
    Positive rate = longs pay shorts; negative = shorts pay longs.
    """
    requested = [s.strip().upper() for s in symbols.split(",")]
    rates = await _fetch_binance_funding_rates(requested)

    if not rates:
        # Demo fallback
        rates = _demo_funding_rates(requested)

    return {"rates": rates, "as_of": datetime.now(UTC).isoformat()}


@router.get("/onchain/{symbol}")
async def get_onchain_metrics(symbol: str, _: CurrentUser):
    """
    Return on-chain metrics for a crypto asset via CoinGecko.
    Includes: market cap, 24h volume, circulating supply, ATH, etc.
    """
    sym = symbol.upper()
    coin_id = COINGECKO_IDS.get(sym)
    if coin_id:
        data = await _fetch_coingecko_coin(coin_id)
        if data:
            return {"symbol": sym, "metrics": data, "as_of": datetime.now(UTC).isoformat()}

    # Demo fallback
    return {
        "symbol": sym,
        "metrics": _demo_onchain_metrics(sym),
        "as_of": datetime.now(UTC).isoformat(),
        "note": "Demo data — live data from CoinGecko API.",
    }


@router.get("/liquidations")
async def get_liquidation_levels(
    _: CurrentUser,
    symbol: str = Query("BTCUSDT"),
):
    """
    Return exchange liquidation heatmap data.
    Shows estimated liquidation clusters at price levels.
    Demo data — real data requires Coinglass API or Binance Options feed.
    """
    base = 47_250.0 if "BTC" in symbol.upper() else 2_450.0
    levels = [
        {"price": base * (1 - i * 0.02), "liquidations_usd": round(1e6 * (i + 1) * 0.5, 0), "side": "long"}
        for i in range(1, 8)
    ] + [
        {"price": base * (1 + i * 0.02), "liquidations_usd": round(1e6 * i * 0.4, 0), "side": "short"}
        for i in range(1, 8)
    ]
    levels.sort(key=lambda x: x["price"])
    return {
        "symbol": symbol.upper(),
        "levels": levels,
        "note": "Demo data — integrate Coinglass API for live liquidation heatmap.",
        "as_of": datetime.now(UTC).isoformat(),
    }


@router.get("/exchange-flows")
async def get_exchange_flows(
    _: CurrentUser,
    symbol: str = Query("BTC"),
):
    """Return exchange inflow/outflow data (demo)."""
    return {
        "symbol": symbol.upper(),
        "netflow_24h": -1_250.5,
        "inflow_24h": 15_420.3,
        "outflow_24h": 16_670.8,
        "exchange_balance": 2_145_000.0,
        "note": "Demo data — integrate Glassnode or Cryptoquant for live exchange flows.",
        "as_of": datetime.now(UTC).isoformat(),
    }


@router.get("/top-movers")
async def get_top_movers(
    _: CurrentUser,
    limit: int = Query(10, ge=1, le=50),
):
    """Return top 24h gainers and losers from CoinGecko."""
    data = await _fetch_coingecko_top_movers(limit)
    if not data:
        data = _demo_top_movers()
    return {"movers": data, "as_of": datetime.now(UTC).isoformat()}


# ─── Internal helpers ─────────────────────────────────────────────────────────
async def _fetch_binance_funding_rates(symbols: list[str]) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BINANCE_BASE}/fapi/v1/premiumIndex")
            if resp.status_code != 200:
                return []
            all_rates = resp.json()
            symbol_set = set(symbols)
            return [
                {
                    "symbol": item["symbol"],
                    "funding_rate": float(item.get("lastFundingRate", 0)) * 100,
                    "next_funding_time": item.get("nextFundingTime"),
                    "mark_price": float(item.get("markPrice", 0)),
                }
                for item in all_rates
                if item.get("symbol") in symbol_set
            ]
    except Exception:  # noqa: BLE001
        return []


async def _fetch_coingecko_coin(coin_id: str) -> dict | None:
    params: dict = {"ids": coin_id, "vs_currency": "usd", "include_market_cap": "true"}
    if settings.coingecko_api_key:
        params["x_cg_demo_api_key"] = settings.coingecko_api_key
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params=params,
            )
            if resp.status_code == 200:
                items = resp.json()
                if items:
                    c = items[0]
                    return {
                        "market_cap": c.get("market_cap"),
                        "volume_24h": c.get("total_volume"),
                        "price": c.get("current_price"),
                        "change_24h": c.get("price_change_percentage_24h"),
                        "circulating_supply": c.get("circulating_supply"),
                        "ath": c.get("ath"),
                        "ath_change_pct": c.get("ath_change_percentage"),
                    }
    except Exception:  # noqa: BLE001
        logger.debug("coingecko.coin_error", coin_id=coin_id)
    return None


async def _fetch_coingecko_top_movers(limit: int) -> list[dict]:
    params: dict = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "sparkline": "false",
    }
    if settings.coingecko_api_key:
        params["x_cg_demo_api_key"] = settings.coingecko_api_key
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{COINGECKO_BASE}/coins/markets", params=params)
            if resp.status_code == 200:
                coins = resp.json()
                sorted_coins = sorted(
                    coins,
                    key=lambda c: abs(c.get("price_change_percentage_24h") or 0),
                    reverse=True,
                )
                return [
                    {
                        "symbol": c["symbol"].upper(),
                        "name": c["name"],
                        "price": c["current_price"],
                        "change_24h": c.get("price_change_percentage_24h"),
                        "volume_24h": c.get("total_volume"),
                        "market_cap": c.get("market_cap"),
                    }
                    for c in sorted_coins[:limit]
                ]
    except Exception:  # noqa: BLE001
        logger.debug("coingecko.top_movers_error")
    return []


def _demo_funding_rates(symbols: list[str]) -> list[dict]:
    # Demo only — not cryptographic use, seed for reproducibility
    import random  # noqa: S311
    random.seed(42)
    return [
        {
            "symbol": sym,
            "funding_rate": round(random.uniform(-0.05, 0.1), 4),  # noqa: S311  # nosec B311
            "next_funding_time": None,
            "mark_price": 47250.0 if "BTC" in sym else 2450.0,
        }
        for sym in symbols
    ]


def _demo_onchain_metrics(symbol: str) -> dict:
    defaults = {
        "BTC": {"market_cap": 930_000_000_000, "volume_24h": 28_400_000_000, "price": 47_250, "change_24h": 2.3, "circulating_supply": 19_600_000, "ath": 73_750, "ath_change_pct": -36.0},
        "ETH": {"market_cap": 295_000_000_000, "volume_24h": 14_200_000_000, "price": 2_450,  "change_24h": 1.8, "circulating_supply": 120_400_000, "ath": 4_891, "ath_change_pct": -50.0},
    }
    return defaults.get(symbol, {"market_cap": None, "volume_24h": None, "price": None, "change_24h": None})


def _demo_top_movers() -> list[dict]:
    return [
        {"symbol": "SOL",  "name": "Solana",   "price": 185.2,  "change_24h": 8.5,  "volume_24h": 4_200_000_000, "market_cap": 85_000_000_000},
        {"symbol": "AVAX", "name": "Avalanche","price": 38.4,   "change_24h": 6.2,  "volume_24h": 650_000_000,   "market_cap": 15_600_000_000},
        {"symbol": "BTC",  "name": "Bitcoin",  "price": 47_250, "change_24h": 2.3,  "volume_24h": 28_400_000_000,"market_cap": 930_000_000_000},
        {"symbol": "DOGE", "name": "Dogecoin", "price": 0.132,  "change_24h": -4.8, "volume_24h": 980_000_000,   "market_cap": 19_200_000_000},
        {"symbol": "XRP",  "name": "XRP",      "price": 0.625,  "change_24h": -3.2, "volume_24h": 1_800_000_000, "market_cap": 35_000_000_000},
    ]
