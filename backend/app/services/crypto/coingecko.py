"""
CoinGecko adapter for cryptocurrency data.

Provides:
  - get_coin_stats(coin_id) → current price, 24h stats, market cap
  - get_ohlcv(coin_id, vs_currency, days) → OHLCV bar list
  - get_top_movers(limit) → top gainers and losers by 24h change

Error handling:
  - No API key required for free tier (public endpoints)
  - HTTP 429 → token-bucket rate limiter (50 calls/min free tier)
  - Timeout 10s
  - Unexpected shape → log + return empty/fallback

Rate limiting: token-bucket with capacity=50, refill_rate=50/60 per second.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_TIMEOUT = 10.0

# Default CoinGecko ID → symbol mapping (subset of major coins)
SYMBOL_TO_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LINK": "chainlink",
}


class _TokenBucket:
    """
    Thread-safe (async-safe) token bucket rate limiter.

    capacity:     maximum tokens (burst size)
    refill_rate:  tokens added per second
    """

    def __init__(self, capacity: float = 50.0, refill_rate: float = 50.0 / 60.0) -> None:
        self._capacity = capacity
        self._tokens = capacity
        self._refill_rate = refill_rate
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            wait = (1.0 - self._tokens) / self._refill_rate
        await asyncio.sleep(wait)
        async with self._lock:
            self._refill()
            self._tokens = max(0.0, self._tokens - 1.0)


# Module-level singleton bucket
_bucket = _TokenBucket()


class CoinGeckoAdapter:
    """CoinGecko REST API adapter with rate limiting and error handling."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"x-cg-pro-api-key": self._api_key}
        return {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        await _bucket.acquire()
        url = f"{_COINGECKO_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params or {}, headers=self._headers())
            if resp.status_code == 429:
                # Bucket should have handled this, but handle server-side throttle too
                wait = float(resp.headers.get("Retry-After", "5"))
                logger.debug("coingecko.rate_limited", wait=wait)
                await asyncio.sleep(wait)
                # Single retry
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, params=params or {}, headers=self._headers())
            if resp.status_code != 200:
                logger.debug("coingecko.http_error", status=resp.status_code, path=path)
                return None
            return resp.json()
        except httpx.TimeoutException:
            logger.debug("coingecko.timeout", path=path)
            return None
        except Exception:  # noqa: BLE001
            logger.debug("coingecko.error", path=path)
            return None

    async def get_coin_stats(self, coin_id: str) -> dict | None:
        """
        Return current price + 24h stats for a coin.

        Output keys: price, market_cap, volume_24h, change_24h, change_pct_24h, ath, symbol
        """
        data = await self._get(
            f"/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
            },
        )
        if not data or not isinstance(data, dict):
            return None
        try:
            md = data.get("market_data", {})
            return {
                "coin_id": coin_id,
                "symbol": data.get("symbol", "").upper(),
                "name": data.get("name", ""),
                "price": md.get("current_price", {}).get("usd"),
                "market_cap": md.get("market_cap", {}).get("usd"),
                "volume_24h": md.get("total_volume", {}).get("usd"),
                "change_pct_24h": md.get("price_change_percentage_24h"),
                "change_24h": md.get("price_change_24h"),
                "circulating_supply": md.get("circulating_supply"),
                "ath": md.get("ath", {}).get("usd"),
            }
        except Exception:  # noqa: BLE001
            logger.debug("coingecko.parse_error", coin_id=coin_id)
            return None

    async def get_ohlcv(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: int = 30,
    ) -> list[dict]:
        """
        Return OHLCV bars for a coin.

        Output: [{"time": unix_ms, "open", "high", "low", "close", "volume"}, ...]
        """
        data = await self._get(
            f"/coins/{coin_id}/ohlc",
            params={"vs_currency": vs_currency, "days": str(days)},
        )
        if not data or not isinstance(data, list):
            return []
        try:
            return [
                {
                    "time": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                }
                for row in data
                if len(row) >= 5
            ]
        except Exception:  # noqa: BLE001
            return []

    async def get_top_movers(self, limit: int = 10) -> dict:
        """
        Return top gainers and losers by 24h % change.

        Output: {"gainers": [...], "losers": [...]}
        """
        data = await self._get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": "250",
                "page": "1",
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
        )
        if not data or not isinstance(data, list):
            return {"gainers": [], "losers": []}

        try:
            coins = [
                {
                    "symbol": c.get("symbol", "").upper(),
                    "name": c.get("name", ""),
                    "price": c.get("current_price"),
                    "change_pct_24h": c.get("price_change_percentage_24h"),
                    "market_cap": c.get("market_cap"),
                }
                for c in data
                if c.get("price_change_percentage_24h") is not None
            ]
            sorted_asc = sorted(coins, key=lambda x: x["change_pct_24h"])
            return {
                "gainers": sorted_asc[-limit:][::-1],
                "losers": sorted_asc[:limit],
            }
        except Exception:  # noqa: BLE001
            return {"gainers": [], "losers": []}
