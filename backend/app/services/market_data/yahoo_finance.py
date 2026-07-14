"""
yfinance provider — polling fallback for historical OHLCV data.

Used when:
  - A paid provider (Alpaca/Polygon) is not configured.
  - Fetching long historical data for backtesting.

Limitations:
  - No real-time data — polls every 30 seconds for intraday (15-min delay).
  - No WebSocket streaming — stream_quotes() yields from polling.
  - Rate limit: ~2000 requests/hour (unofficial API).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
import yfinance as yf

from app.data.ingestion.normalizer import CanonicalBar, CanonicalQuote, infer_asset_class
from app.services.market_data.base import MarketDataProvider

logger = structlog.get_logger(__name__)

# yfinance interval mapping
_TF_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",  # yfinance has no 4h — we resample from 1h downstream
    "1d": "1d",
    "1w": "1wk",
}


def _yf_symbol(symbol: str) -> str:
    """Convert canonical symbol to yfinance format."""
    # BTC-USD → BTC-USD (already compatible)
    # EURUSD → EURUSD=X (forex)
    s = symbol.upper()
    if re.match(r"^[A-Z]{6}$", s):
        return f"{s}=X"
    return s


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 500,
    ) -> list[CanonicalBar]:
        interval = _TF_MAP.get(timeframe, "1d")
        yf_sym = _yf_symbol(symbol)
        asset_class = infer_asset_class(symbol)

        try:
            ticker = yf.Ticker(yf_sym)
            if start or end:
                df = ticker.history(interval=interval, start=start, end=end)
            else:
                # Compute a sensible default period
                period = "60d" if interval in ("1m", "5m", "15m") else "2y"
                df = ticker.history(interval=interval, period=period)

            if df.empty:
                return []

            # Take the last `limit` rows
            df = df.tail(limit)
            bars = []
            for ts, row in df.iterrows():
                bars.append(
                    CanonicalBar(
                        time=ts.to_pydatetime().replace(tzinfo=UTC),  # type: ignore[union-attr]
                        symbol=symbol.upper(),
                        exchange="UNKNOWN",
                        asset_class=asset_class,
                        timeframe=timeframe,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row.get("Volume", 0)),
                        provider=self.name,
                    )
                )
            return bars

        except Exception:
            logger.exception("yfinance.get_bars.error", symbol=symbol)
            return []

    async def get_quote(self, symbol: str) -> CanonicalQuote | None:
        yf_sym = _yf_symbol(symbol)
        try:
            ticker = yf.Ticker(yf_sym)
            info = ticker.fast_info
            price = float(info.last_price or 0)
            prev_close = float(info.previous_close or 0)
            change = price - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0
            return CanonicalQuote(
                symbol=symbol.upper(),
                price=price,
                volume=float(info.three_month_average_volume or 0),
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(UTC),
                provider=self.name,
                asset_class=infer_asset_class(symbol),
            )
        except Exception:
            logger.exception("yfinance.get_quote.error", symbol=symbol)
            return None

    async def get_quotes(self, symbols: list[str]) -> dict[str, CanonicalQuote | None]:
        results: dict[str, CanonicalQuote | None] = {}
        for sym in symbols:
            results[sym] = await self.get_quote(sym)
            await asyncio.sleep(0.1)  # light rate limit
        return results

    async def stream_quotes(self, symbols: list[str]) -> AsyncGenerator[CanonicalQuote, None]:
        """Poll yfinance every 30 seconds — best-effort real-time simulation."""
        while True:
            for sym in symbols:
                quote = await self.get_quote(sym)
                if quote:
                    yield quote
            await asyncio.sleep(30)

    async def search_symbols(self, query: str) -> list[dict]:
        """yfinance does not support symbol search — return empty."""
        return []
