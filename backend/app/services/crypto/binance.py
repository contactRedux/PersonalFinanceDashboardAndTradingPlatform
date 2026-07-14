"""
Binance (binance.us) adapter for crypto trading data.

Provides:
  - get_ticker(symbol) → 24hr price statistics
  - get_order_book(symbol, limit) → bid/ask ladder (default depth 20)
  - get_recent_trades(symbol, limit) → last N trades
  - get_klines(symbol, interval, limit) → OHLCV candlestick bars

Error handling:
  - HTTP 429 → exponential backoff, max 2 retries
  - Timeout 10s → returns empty structure
  - Unexpected response shape → logs + returns empty structure
  - No API key required for public endpoints
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_BINANCE_BASE = "https://api.binance.us"
_TIMEOUT = 10.0
_MAX_RETRIES = 2

# Kline interval mapping
_VALID_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


class BinanceAdapter:
    """
    Binance.us public REST API adapter.

    Public endpoints (ticker, orderbook, trades, klines) require no authentication.
    """

    def __init__(self, api_key: str | None = None, secret: str | None = None) -> None:
        self._api_key = api_key
        self._secret = secret

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"X-MBX-APIKEY": self._api_key}
        return {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{_BINANCE_BASE}{path}"
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, params=params or {}, headers=self._headers())
                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        backoff = 2.0 ** attempt
                        logger.debug("binance.rate_limited", attempt=attempt, backoff=backoff)
                        await asyncio.sleep(backoff)
                        continue
                    logger.warning("binance.rate_limit_exceeded")
                    return None
                if resp.status_code != 200:
                    logger.debug("binance.http_error", status=resp.status_code, path=path)
                    return None
                return resp.json()
            except httpx.TimeoutException:
                logger.debug("binance.timeout", path=path)
                return None
            except Exception:  # noqa: BLE001
                logger.debug("binance.error", path=path)
                return None
        return None

    async def get_ticker(self, symbol: str) -> dict | None:
        """
        Return 24-hour price statistics for a symbol.

        Output: {symbol, price, change, change_pct, volume, high, low, ...}
        """
        data = await self._get("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
        if not data or not isinstance(data, dict):
            return None
        try:
            return {
                "symbol": data.get("symbol", symbol.upper()),
                "price": float(data.get("lastPrice", 0)),
                "change": float(data.get("priceChange", 0)),
                "change_pct": float(data.get("priceChangePercent", 0)),
                "volume": float(data.get("volume", 0)),
                "quote_volume": float(data.get("quoteVolume", 0)),
                "high_24h": float(data.get("highPrice", 0)),
                "low_24h": float(data.get("lowPrice", 0)),
                "open": float(data.get("openPrice", 0)),
                "bid": float(data.get("bidPrice", 0)),
                "ask": float(data.get("askPrice", 0)),
                "trade_count": int(data.get("count", 0)),
            }
        except (ValueError, TypeError):
            logger.debug("binance.ticker_parse_error", symbol=symbol)
            return None

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """
        Return order book depth (bids + asks).

        Output: {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}
        """
        data = await self._get("/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})
        if not data or not isinstance(data, dict):
            return {"bids": [], "asks": []}
        return {
            "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
            "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
            "last_update_id": data.get("lastUpdateId"),
        }

    async def get_recent_trades(self, symbol: str, limit: int = 50) -> list[dict]:
        """
        Return recent trades for a symbol.

        Output: [{"id", "price", "qty", "time", "is_buyer_maker"}, ...]
        """
        data = await self._get("/api/v3/trades", {"symbol": symbol.upper(), "limit": limit})
        if not data or not isinstance(data, list):
            return []
        try:
            return [
                {
                    "id": t.get("id"),
                    "price": float(t.get("price", 0)),
                    "qty": float(t.get("qty", 0)),
                    "time": t.get("time"),
                    "is_buyer_maker": t.get("isBuyerMaker", False),
                }
                for t in data
            ]
        except Exception:  # noqa: BLE001
            return []

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
    ) -> list[dict]:
        """
        Return OHLCV candlestick data.

        Output: [{"open_time", "open", "high", "low", "close", "volume", "close_time"}, ...]
        """
        if interval not in _VALID_INTERVALS:
            interval = "1d"
        data = await self._get(
            "/api/v3/klines",
            {"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        if not data or not isinstance(data, list):
            return []
        try:
            return [
                {
                    "open_time": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "close_time": row[6],
                    "quote_volume": float(row[7]),
                    "trade_count": int(row[8]),
                }
                for row in data
                if len(row) >= 9
            ]
        except Exception:  # noqa: BLE001
            return []
