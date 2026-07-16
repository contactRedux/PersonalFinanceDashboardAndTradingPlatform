"""
OANDA Forex market data provider.

Implements the `MarketDataProvider` abstract interface using the OANDA v20 REST API.
Supports forex pairs (EUR_USD, GBP_USD, etc.) and CFDs available on the OANDA platform.

Configuration (from environment variables):
  OANDA_API_KEY      — OANDA personal access token
  OANDA_ACCOUNT_ID   — OANDA account ID (e.g. 001-001-12345678-001)
  OANDA_BASE_URL     — API base URL
                       Practice: https://api-fxpractice.oanda.com
                       Live:     https://api-fxtrade.oanda.com

OANDA instrument format: EUR_USD, GBP_JPY, etc. (underscore-separated).
If a symbol is passed as EUR/USD or EURUSD, it is normalised automatically.

Rate limits:
  REST: 120 requests/second per IP (no daily quota)
  Streaming: 2 concurrent streaming connections
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings
from app.data.ingestion.normalizer import CanonicalBar, CanonicalQuote, infer_asset_class
from app.services.market_data.base import MarketDataProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_GRANULARITY_MAP = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
    "1w": "W",
}


def _normalise_symbol(symbol: str) -> str:
    """Convert EUR/USD or EURUSD → EUR_USD (OANDA format)."""
    sym = symbol.upper()
    if "/" in sym:
        return sym.replace("/", "_")
    # Handle 6-char forex pairs without delimiter (e.g. EURUSD → EUR_USD)
    if "_" not in sym and len(sym) == 6:
        return f"{sym[:3]}_{sym[3:]}"
    return sym


def _oanda_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.oanda_api_key}",
        "Content-Type": "application/json",
        "Accept-Datetime-Format": "RFC3339",
    }


class OANDAProvider(MarketDataProvider):
    """Market data provider backed by the OANDA v20 REST API (forex focus)."""

    name = "oanda"

    def _is_available(self) -> bool:
        return bool(settings.oanda_api_key and settings.oanda_account_id)

    @property
    def _base_url(self) -> str:
        return settings.oanda_base_url.rstrip("/")

    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 500,
    ) -> list[CanonicalBar]:
        if not self._is_available():
            return []

        instrument = _normalise_symbol(symbol)
        granularity = _GRANULARITY_MAP.get(timeframe, "D")

        params: dict = {
            "granularity": granularity,
            "count": min(limit, 5000),
            "price": "M",  # midpoint candles
        }
        if start:
            params["from"] = start
            params.pop("count", None)
        if end:
            params["to"] = end

        url = f"{self._base_url}/v3/instruments/{instrument}/candles"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=_oanda_headers())
                resp.raise_for_status()
                data = resp.json()

            candles = data.get("candles", [])
            bars: list[CanonicalBar] = []
            for c in candles:
                if not c.get("complete", True):
                    continue
                mid = c.get("mid", {})
                bars.append(
                    CanonicalBar(
                        time=datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                        symbol=instrument,
                        exchange="OANDA",
                        asset_class="forex",
                        timeframe=timeframe,
                        open=float(mid.get("o", 0)),
                        high=float(mid.get("h", 0)),
                        low=float(mid.get("l", 0)),
                        close=float(mid.get("c", 0)),
                        volume=float(c.get("volume", 0)),
                        vwap=None,
                        trade_count=int(c.get("volume", 0)),
                        provider=self.name,
                    )
                )
            return bars
        except Exception:
            logger.exception("oanda.get_bars.error", symbol=instrument)
            return []

    async def get_quote(self, symbol: str) -> CanonicalQuote | None:
        quotes = await self.get_quotes([symbol])
        return quotes.get(_normalise_symbol(symbol))

    async def get_quotes(self, symbols: list[str]) -> dict[str, CanonicalQuote | None]:
        if not self._is_available():
            return dict.fromkeys(symbols)

        instruments = [_normalise_symbol(s) for s in symbols]
        url = f"{self._base_url}/v3/accounts/{settings.oanda_account_id}/pricing"
        params = {"instruments": ",".join(instruments)}

        results: dict[str, CanonicalQuote | None] = {
            _normalise_symbol(s): None for s in symbols
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=_oanda_headers())
                resp.raise_for_status()
                data = resp.json()

            now = datetime.now(UTC)
            for price in data.get("prices", []):
                instrument = price.get("instrument", "")
                bids = price.get("bids", [{}])
                asks = price.get("asks", [{}])
                bid = float(bids[0].get("price", 0)) if bids else 0.0
                ask = float(asks[0].get("price", 0)) if asks else 0.0
                mid = (bid + ask) / 2 if (bid and ask) else bid or ask

                ts_raw = price.get("time", now.isoformat())
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = now

                results[instrument] = CanonicalQuote(
                    symbol=instrument,
                    price=mid,
                    bid=bid,
                    ask=ask,
                    bid_size=float(bids[0].get("liquidity", 0)) if bids else 0.0,
                    ask_size=float(asks[0].get("liquidity", 0)) if asks else 0.0,
                    timestamp=ts,
                    provider=self.name,
                    asset_class="forex",
                )
        except Exception:
            logger.exception("oanda.get_quotes.error")

        return results

    async def stream_quotes(self, symbols: list[str]) -> AsyncGenerator[CanonicalQuote, None]:
        """
        Stream real-time quotes from OANDA pricing stream endpoint.

        Reconnects automatically on network errors with 5-second backoff.
        """
        if not self._is_available():
            return

        instruments = [_normalise_symbol(s) for s in symbols]
        stream_url = (
            self._base_url.replace("api-fx", "stream-fx")
            + f"/v3/accounts/{settings.oanda_account_id}/pricing/stream"
        )
        params = {"instruments": ",".join(instruments)}

        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "GET",
                        stream_url,
                        params=params,
                        headers=_oanda_headers(),
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                import json  # noqa: PLC0415
                                msg = json.loads(line)
                            except (ValueError, Exception):  # noqa: BLE001
                                continue

                            if msg.get("type") != "PRICE":
                                continue

                            instrument = msg.get("instrument", "")
                            bids = msg.get("bids", [{}])
                            asks = msg.get("asks", [{}])
                            bid = float(bids[0].get("price", 0)) if bids else 0.0
                            ask = float(asks[0].get("price", 0)) if asks else 0.0
                            mid = (bid + ask) / 2 if (bid and ask) else bid or ask

                            ts_raw = msg.get("time", datetime.now(UTC).isoformat())
                            try:
                                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                            except ValueError:
                                ts = datetime.now(UTC)

                            yield CanonicalQuote(
                                symbol=instrument,
                                price=mid,
                                bid=bid,
                                ask=ask,
                                bid_size=float(bids[0].get("liquidity", 0)) if bids else 0.0,
                                ask_size=float(asks[0].get("liquidity", 0)) if asks else 0.0,
                                timestamp=ts,
                                provider=self.name,
                                asset_class="forex",
                            )
            except Exception:
                logger.warning("oanda.stream.reconnect", symbols=instruments)
                await asyncio.sleep(5)

    async def search_symbols(self, query: str) -> list[dict]:
        """
        Search OANDA instruments by name or currency code.

        Returns a filtered list from the full instrument catalogue.
        """
        if not self._is_available():
            return []

        url = f"{self._base_url}/v3/accounts/{settings.oanda_account_id}/instruments"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=_oanda_headers())
                resp.raise_for_status()
                data = resp.json()

            q_upper = query.upper()
            matches = []
            for inst in data.get("instruments", []):
                name = inst.get("name", "")
                display = inst.get("displayName", "")
                if q_upper in name or q_upper in display.upper():
                    matches.append({
                        "symbol": name,
                        "name": display,
                        "exchange": "OANDA",
                        "asset_class": "forex",
                        "type": inst.get("type", "CURRENCY"),
                    })
            return matches[:20]
        except Exception:
            logger.exception("oanda.search.error")
            return []
