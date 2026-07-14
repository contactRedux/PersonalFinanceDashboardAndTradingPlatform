"""Market data REST endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.data.cache.quote_cache import get_quotes, set_quote
from app.dependencies import CurrentUser
from app.services.market_data.router import get_provider

router = APIRouter()


# ─── Response schemas ─────────────────────────────────────────────────────────
class QuoteResponse(BaseModel):
    symbol: str
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    change: float | None = None
    change_pct: float | None = None
    timestamp: str | None = None
    provider: str | None = None
    asset_class: str | None = None


class BarResponse(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/quotes")
async def get_batch_quotes(
    _: CurrentUser,
    symbols: str = Query(..., description="Comma-separated symbols e.g. AAPL,MSFT,BTC-USD"),
):
    """Return latest quotes for a batch of symbols from Redis cache (or live fetch)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    # Try Redis cache first
    cached = await get_quotes(symbol_list)
    missing = [s for s, v in cached.items() if v is None]

    # Fetch any missing quotes from the provider
    if missing:
        provider = get_provider()
        live = await provider.get_quotes(missing)
        for sym, quote in live.items():
            if quote:
                q_dict = quote.to_dict()
                await set_quote(sym, q_dict)
                cached[sym] = q_dict

    return {"quotes": cached}


@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str,
    _: CurrentUser,
    timeframe: str = Query("1d", description="1m|5m|15m|1h|4h|1d|1w"),
    start: str | None = Query(None, description="ISO datetime"),
    end: str | None = Query(None, description="ISO datetime"),
    limit: int = Query(500, ge=1, le=5000),
):
    """Return OHLCV bars for a symbol."""
    provider = get_provider()
    bars = await provider.get_bars(symbol, timeframe, start=start, end=end, limit=limit)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "bars": [
            BarResponse(
                time=b.time.isoformat(),
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                vwap=b.vwap,
            ).model_dump()
            for b in bars
        ],
        "count": len(bars),
    }


@router.get("/search")
async def search_symbols(
    _: CurrentUser,
    q: str = Query(..., min_length=1, max_length=50),
    asset_class: str | None = Query(None, description="equity|crypto|forex|futures|options"),
):
    """Search for symbols by name or ticker."""
    provider = get_provider()
    results = await provider.search_symbols(q)
    if asset_class:
        results = [r for r in results if r.get("asset_class") == asset_class]
    return {"results": results, "count": len(results)}


@router.get("/snapshot/{symbol}")
async def get_snapshot(symbol: str, _: CurrentUser):
    """Full snapshot: quote + provider info."""
    sym = symbol.upper()
    cached = await get_quotes([sym])
    quote = cached.get(sym)

    if not quote:
        provider = get_provider()
        live = await provider.get_quote(sym)
        if live:
            quote = live.to_dict()
            await set_quote(sym, quote)

    return {
        "symbol": sym,
        "quote": quote,
        "timestamp": datetime.now(UTC).isoformat(),
    }
