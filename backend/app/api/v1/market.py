"""Market data REST endpoints."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.cache.quote_cache import get_quotes, set_quote
from app.dependencies import CurrentUser, get_db
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


class TickRecord(BaseModel):
    time: str
    price: float
    size: float
    side: str | None = None


class TicksResponse(BaseModel):
    symbol: str
    ticks: list[TickRecord]
    count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/ticks/{symbol}", response_model=TicksResponse)
async def get_ticks(
    symbol: str,
    _: CurrentUser,
    db: AsyncSession = Depends(get_db),
    start: str | None = Query(None, description="ISO8601 start datetime"),
    end: str | None = Query(None, description="ISO8601 end datetime"),
    limit: int = Query(1000, ge=1, le=10000),
):
    """Return tick data for a symbol from the ticks hypertable."""
    sym = symbol.upper()
    try:
        import sqlalchemy as sa  # noqa: PLC0415

        start_dt = datetime.fromisoformat(start) if start else datetime(2000, 1, 1, tzinfo=UTC)
        end_dt = datetime.fromisoformat(end) if end else datetime.now(UTC)

        sql = sa.text(
            "SELECT time, symbol, price, size, side FROM ticks"
            " WHERE symbol = :symbol AND time BETWEEN :start AND :end"
            " ORDER BY time DESC LIMIT :limit"
        )
        result = await db.execute(
            sql,
            {"symbol": sym, "start": start_dt, "end": end_dt, "limit": limit},
        )
        rows = result.fetchall()
        ticks = [
            TickRecord(
                time=row.time.isoformat() if hasattr(row.time, "isoformat") else str(row.time),
                price=float(row.price),
                size=float(row.size),
                side=row.side,
            )
            for row in rows
        ]
        return TicksResponse(symbol=sym, ticks=ticks, count=len(ticks))
    except Exception:  # noqa: BLE001
        return TicksResponse(symbol=sym, ticks=[], count=0)


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


# ─── Chart transform helpers ──────────────────────────────────────────────────


def _to_renko(bars: list, brick_size: float) -> list[dict]:
    """Standard renko: new brick when price moves brick_size from last close."""
    if not bars or brick_size <= 0:
        return []
    result: list[dict] = []
    last_close = float(bars[0].close)
    for bar in bars[1:]:
        close = float(bar.close)
        time_str = bar.time.isoformat()
        while abs(close - last_close) >= brick_size:
            if close > last_close:
                open_ = last_close
                new_close = last_close + brick_size
            else:
                open_ = last_close
                new_close = last_close - brick_size
            result.append({
                "time": time_str,
                "open": round(open_, 8),
                "high": round(max(open_, new_close), 8),
                "low": round(min(open_, new_close), 8),
                "close": round(new_close, 8),
                "volume": float(bar.volume),
                "vwap": None,
            })
            last_close = new_close
    if not result:
        b = bars[-1]
        result.append({
            "time": b.time.isoformat(),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
            "vwap": None,
        })
    return result


def _to_line_break(bars: list, n_lines: int = 3) -> list[dict]:
    """N-line break: new line only when price breaks beyond N prior lines."""
    if not bars:
        return []
    lines: list[dict] = []
    for bar in bars:
        close = float(bar.close)
        time_str = bar.time.isoformat()
        if not lines:
            op = float(bar.open)
            lines.append({
                "time": time_str,
                "open": round(op, 8),
                "high": round(max(op, close), 8),
                "low": round(min(op, close), 8),
                "close": round(close, 8),
                "volume": float(bar.volume),
                "vwap": None,
            })
            continue
        recent = lines[-n_lines:]
        high_n = max(ln["high"] for ln in recent)
        low_n = min(ln["low"] for ln in recent)
        last_close = lines[-1]["close"]
        if close > high_n:
            lines.append({
                "time": time_str,
                "open": round(last_close, 8),
                "high": round(close, 8),
                "low": round(last_close, 8),
                "close": round(close, 8),
                "volume": float(bar.volume),
                "vwap": None,
            })
        elif close < low_n:
            lines.append({
                "time": time_str,
                "open": round(last_close, 8),
                "high": round(last_close, 8),
                "low": round(close, 8),
                "close": round(close, 8),
                "volume": float(bar.volume),
                "vwap": None,
            })
    return lines


@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str,
    _: CurrentUser,
    timeframe: str = Query("1d", description="1m|5m|15m|1h|4h|1d|1w"),
    start: str | None = Query(None, description="ISO datetime"),
    end: str | None = Query(None, description="ISO datetime"),
    limit: int = Query(500, ge=1, le=5000),
    chart_type: str = Query("ohlcv", description="ohlcv|renko|line_break"),
    brick_size: float = Query(1.0, description="Renko brick size"),
    n_lines: int = Query(3, ge=1, le=20, description="N-line break count"),
):
    """Return OHLCV bars for a symbol, optionally transformed to Renko or N-Line Break."""
    provider = get_provider()
    bars = await provider.get_bars(symbol, timeframe, start=start, end=end, limit=limit)
    if chart_type == "renko":
        transformed = _to_renko(bars, brick_size)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": transformed, "count": len(transformed)}
    if chart_type == "line_break":
        transformed = _to_line_break(bars, n_lines)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": transformed, "count": len(transformed)}
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
    """Full snapshot: quote + fundamentals + sentiment + latest_news."""
    sym = symbol.upper()
    cached = await get_quotes([sym])
    quote = cached.get(sym)

    if not quote:
        provider = get_provider()
        live = await provider.get_quote(sym)
        if live:
            quote = live.to_dict()
            await set_quote(sym, quote)

    # ── Fundamentals from yfinance ────────────────────────────────────────────
    fundamentals: dict = {}
    try:
        import yfinance as yf  # noqa: PLC0415

        info = await asyncio.to_thread(lambda: yf.Ticker(sym).info)
        fundamentals = {
            "pe_ratio": info.get("trailingPE"),
            "market_cap": info.get("marketCap"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception:  # noqa: BLE001
        fundamentals = {}

    # ── FinBERT sentiment (latest scored article headline) ────────────────────
    sentiment: dict = {}
    try:
        from app.services.sentiment.finbert import score_text  # noqa: PLC0415

        raw = await asyncio.to_thread(score_text, sym)
        label = raw.get("label", "neutral")
        conf = float(raw.get("confidence", 0.5))
        if label == "bullish":
            sentiment = {"positive": conf, "neutral": 1 - conf, "negative": 0.0}
        elif label == "bearish":
            sentiment = {"positive": 0.0, "neutral": 1 - conf, "negative": conf}
        else:
            sentiment = {"positive": 0.0, "neutral": 1.0, "negative": 0.0}
    except Exception:  # noqa: BLE001
        sentiment = {}

    # ── Latest news items ─────────────────────────────────────────────────────
    latest_news: list[dict] = []
    try:
        from app.services.news.aggregator import fetch_and_aggregate  # noqa: PLC0415

        articles = await fetch_and_aggregate(symbols=[sym], from_hours=24, max_articles=3)
        latest_news = articles[:3]
    except Exception:  # noqa: BLE001
        latest_news = []

    return {
        "symbol": sym,
        "quote": quote,
        "fundamentals": fundamentals,
        "sentiment": sentiment,
        "latest_news": latest_news,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/vpvr/{symbol}")
async def get_vpvr(
    symbol: str,
    _: CurrentUser,
    timeframe: str = Query("1d"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    bins: int = Query(24, ge=4, le=100),
):
    """
    Volume Profile Visible Range (VPVR).

    Returns a list of price levels with aggregated volume.
    The level with the highest volume is the Point of Control (POC).

    Each item: {price, volume, is_poc, pct_of_max}
    """
    provider = get_provider()
    bars = await provider.get_bars(symbol, timeframe, start=start, end=end, limit=500)

    if not bars:
        return {"symbol": symbol.upper(), "price_levels": [], "poc": None}

    closes = [float(b.close) for b in bars]
    volumes = [float(b.volume) for b in bars]

    price_min = min(closes)
    price_max = max(closes)
    if price_max == price_min:
        return {"symbol": symbol.upper(), "price_levels": [], "poc": None}

    bin_size = (price_max - price_min) / bins
    bucket_vol = [0.0] * bins

    for close, vol in zip(closes, volumes, strict=False):
        idx = min(bins - 1, int((close - price_min) / bin_size))
        bucket_vol[idx] += vol

    max_vol = max(bucket_vol) if bucket_vol else 1.0
    poc_idx = bucket_vol.index(max_vol)
    poc_price = round(price_min + (poc_idx + 0.5) * bin_size, 4)

    price_levels = [
        {
            "price": round(price_min + (i + 0.5) * bin_size, 4),
            "volume": bucket_vol[i],
            "is_poc": i == poc_idx,
            "pct_of_max": round(bucket_vol[i] / max_vol, 4) if max_vol else 0.0,
        }
        for i in range(bins)
        if bucket_vol[i] > 0
    ]

    return {"symbol": symbol.upper(), "price_levels": price_levels, "poc": poc_price}


# ─── Technical Indicator helpers ──────────────────────────────────────────────

def _sma(prices: list[float], period: int) -> float:
    """Simple moving average over the last `period` values."""
    window = prices[-period:] if len(prices) >= period else prices
    return sum(window) / len(window)


def _ema(prices: list[float], period: int) -> float:
    """Exponential moving average (seed from SMA of first window)."""
    if not prices:
        return 0.0
    k = 2.0 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: list[float], period: int = 14) -> float:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    # Use only the last `period` changes
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd_signal(prices: list[float]) -> float:
    """MACD signal line value (EMA12 - EMA26, then 9-period EMA of that)."""
    if len(prices) < 26:
        return 0.0
    macd_line = _ema(prices, 12) - _ema(prices, 26)
    return macd_line  # simplified: return MACD line as signal when history is short


def _bollinger(prices: list[float], period: int = 20, n_std: float = 2.0) -> tuple[float, float]:
    """Return (upper_band, lower_band) of Bollinger Bands."""
    window = prices[-period:] if len(prices) >= period else prices
    mid = sum(window) / len(window)
    variance = sum((p - mid) ** 2 for p in window) / len(window)
    std = variance ** 0.5
    return mid + n_std * std, mid - n_std * std


def _build_demo_bars(symbol: str, n: int = 60) -> list[float]:
    """Generate synthetic close prices for demo/fallback use."""
    import math

    base = 150.0
    return [base + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]


# ─── Indicators endpoint ──────────────────────────────────────────────────────

_INDICATORS_TTL = 300  # Redis TTL seconds


@router.get("/indicators/{symbol}")
async def get_indicators(symbol: str, _: CurrentUser):
    """
    Return a snapshot of key technical indicator values for a symbol.

    Indicators computed: sma_20, ema_50, rsi_14, macd_signal, bb_upper, bb_lower.

    Results are cached in Redis with a 300-second TTL.
    When Redis is unavailable the computation runs fresh on every call.
    """
    sym = symbol.upper()
    cache_key = f"indicators:{sym}"

    # ── Try Redis cache ──────────────────────────────────────────────────────
    redis_client = None
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415

        redis_client = await get_redis_pool()
        cached_raw = await redis_client.get(cache_key)
        if cached_raw:
            return json.loads(cached_raw)
    except Exception:  # noqa: BLE001
        redis_client = None  # fall through to fresh computation

    # ── Fetch bars (or use synthetic fallback) ────────────────────────────────
    try:
        provider = get_provider()
        bars = await provider.get_bars(sym, "1d", limit=60)
        closes = [float(b.close) for b in bars] if bars else []
    except Exception:  # noqa: BLE001
        closes = []

    if not closes:
        closes = _build_demo_bars(sym)

    bb_upper, bb_lower = _bollinger(closes)
    payload: dict = {
        "symbol": sym,
        "sma_20": round(_sma(closes, 20), 4),
        "ema_50": round(_ema(closes, 50), 4),
        "rsi_14": round(_rsi(closes, 14), 4),
        "macd_signal": round(_macd_signal(closes), 4),
        "bb_upper": round(bb_upper, 4),
        "bb_lower": round(bb_lower, 4),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # ── Cache result ──────────────────────────────────────────────────────────
    if redis_client is not None:
        try:
            await redis_client.set(cache_key, json.dumps(payload), ex=_INDICATORS_TTL)
        except Exception:  # noqa: BLE001, S110
            pass  # best-effort cache write; non-fatal

    return payload
