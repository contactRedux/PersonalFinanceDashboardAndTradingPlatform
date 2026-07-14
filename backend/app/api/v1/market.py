"""Market data REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.data.cache.quote_cache import get_quotes
from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/quotes")
async def get_batch_quotes(
    symbols: str = Query(..., description="Comma-separated symbols e.g. AAPL,MSFT,BTC-USD"),
    _: dict = CurrentUser,
):
    """Return latest quotes for a batch of symbols from Redis cache."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    data = await get_quotes(symbol_list)
    return {"quotes": data}


@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str,
    timeframe: str = Query("1d", description="1m|5m|15m|1h|4h|1d|1w"),
    start: str | None = Query(None, description="ISO datetime"),
    end: str | None = Query(None, description="ISO datetime"),
    limit: int = Query(500, ge=1, le=5000),
    _: dict = CurrentUser,
):
    """Return OHLCV bars for a symbol from TimescaleDB."""
    # Implemented in ST-5 (market data layer)
    return {
        "symbol": symbol.upper(), "timeframe": timeframe,
        "bars": [], "note": "Data layer in ST-5",
    }


@router.get("/search")
async def search_symbols(
    q: str = Query(..., min_length=1, max_length=50),
    asset_class: str | None = Query(None, description="equity|crypto|forex|futures|options"),
    _: dict = CurrentUser,
):
    """Search for symbols by name or ticker."""
    # Implemented in ST-5
    return {"results": [], "note": "Symbol search in ST-5"}


@router.get("/snapshot/{symbol}")
async def get_snapshot(symbol: str, _: dict = CurrentUser):
    """Full snapshot: quote + fundamentals + sentiment summary."""
    quotes = await get_quotes([symbol.upper()])
    return {"symbol": symbol.upper(), "quote": quotes.get(symbol.upper())}
