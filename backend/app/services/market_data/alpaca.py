"""
Alpaca Markets provider — WebSocket streaming + REST API.

Supports:
  - Real-time quotes via Alpaca WebSocket (IEX free tier or SIP paid)
  - Historical OHLCV bars via REST API
  - Both US equities and crypto (via separate endpoints)

Configuration (from environment variables):
  ALPACA_API_KEY     — API key ID
  ALPACA_API_SECRET  — API secret key
  ALPACA_BASE_URL    — Override for paper/live trading endpoint
  ALPACA_WS_URL      — WebSocket URL (default: wss://stream.data.alpaca.markets/v2/iex)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import structlog
import websockets

from app.config import get_settings
from app.data.ingestion.normalizer import CanonicalBar, CanonicalQuote, infer_asset_class
from app.services.market_data.base import MarketDataProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_ALPACA_REST_BASE = "https://data.alpaca.markets/v2"
_ALPACA_WS_STOCKS = "wss://stream.data.alpaca.markets/v2/iex"
_ALPACA_WS_CRYPTO = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"

_TF_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "1h": "1Hour",
    "4h": "4Hour",
    "1d": "1Day",
    "1w": "1Week",
}


def _alpaca_secret() -> str:
    """Return the configured Alpaca secret key (prefer alpaca_api_secret)."""
    return settings.alpaca_api_secret or settings.alpaca_secret_key or ""


def _alpaca_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key or "",
        "APCA-API-SECRET-KEY": _alpaca_secret(),
        "Accept": "application/json",
    }


class AlpacaProvider(MarketDataProvider):
    name = "alpaca"

    def _is_available(self) -> bool:
        return bool(settings.alpaca_api_key and _alpaca_secret())

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

        tf = _TF_MAP.get(timeframe, "1Day")
        asset_class = infer_asset_class(symbol)
        sym_upper = symbol.upper()

        params: dict = {"limit": limit, "timeframe": tf, "sort": "asc"}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        # Different endpoints for crypto vs equities
        if asset_class == "crypto":
            url = f"{_ALPACA_REST_BASE}/crypto/us/bars"
            params["symbols"] = sym_upper
        else:
            url = f"{_ALPACA_REST_BASE}/stocks/bars"
            params["symbols"] = sym_upper

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=_alpaca_headers())
                resp.raise_for_status()
                data = resp.json()

            bars_data = data.get("bars", {}).get(sym_upper, [])
            bars = []
            for b in bars_data:
                bars.append(
                    CanonicalBar(
                        time=datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                        symbol=sym_upper,
                        exchange=b.get("x", "ALPACA"),
                        asset_class=asset_class,
                        timeframe=timeframe,
                        open=float(b["o"]),
                        high=float(b["h"]),
                        low=float(b["l"]),
                        close=float(b["c"]),
                        volume=float(b["v"]),
                        vwap=float(b["vw"]) if b.get("vw") else None,
                        trade_count=int(b["n"]) if b.get("n") else None,
                        provider=self.name,
                    )
                )
            return bars
        except Exception:
            logger.exception("alpaca.get_bars.error", symbol=symbol)
            return []

    async def get_quote(self, symbol: str) -> CanonicalQuote | None:
        quotes = await self.get_quotes([symbol])
        return quotes.get(symbol)

    async def get_quotes(self, symbols: list[str]) -> dict[str, CanonicalQuote | None]:
        if not self._is_available():
            return dict.fromkeys(symbols)

        results: dict[str, CanonicalQuote | None] = dict.fromkeys(symbols)

        # Separate equities from crypto
        equity_syms = [s for s in symbols if infer_asset_class(s) != "crypto"]
        crypto_syms = [s for s in symbols if infer_asset_class(s) == "crypto"]

        async def _fetch(url: str, sym_list: list[str]) -> None:
            if not sym_list:
                return
            params = {"symbols": ",".join(sym_list)}
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, params=params, headers=_alpaca_headers())
                    resp.raise_for_status()
                    data = resp.json()
                for sym, q in data.get("quotes", {}).items():
                    results[sym] = CanonicalQuote(
                        symbol=sym,
                        price=float(q.get("ap", q.get("bp", 0))),
                        bid=float(q.get("bp", 0)),
                        ask=float(q.get("ap", 0)),
                        bid_size=float(q.get("bs", 0)),
                        ask_size=float(q.get("as", 0)),
                        timestamp=datetime.fromisoformat(
                            q.get("t", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
                        ),
                        provider=self.name,
                        asset_class=infer_asset_class(sym),
                    )
            except Exception:
                logger.exception("alpaca.get_quotes.error")

        await asyncio.gather(
            _fetch(f"{_ALPACA_REST_BASE}/stocks/quotes/latest", equity_syms),
            _fetch(f"{_ALPACA_REST_BASE}/crypto/us/quotes/latest", crypto_syms),
        )
        return results

    async def stream_quotes(self, symbols: list[str]) -> AsyncGenerator[CanonicalQuote, None]:
        if not self._is_available():
            return

        # Separate equity and crypto symbols
        equity_syms = [s for s in symbols if infer_asset_class(s) != "crypto"]
        crypto_syms = [s for s in symbols if infer_asset_class(s) == "crypto"]

        ws_url = _ALPACA_WS_STOCKS if equity_syms else _ALPACA_WS_CRYPTO
        sub_syms = equity_syms or crypto_syms

        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    # Authenticate
                    await ws.send(
                        json.dumps(
                            {
                                "action": "auth",
                                "key": settings.alpaca_api_key,
                                "secret": _alpaca_secret(),
                            }
                        )
                    )
                    await ws.recv()  # auth response

                    # Subscribe to quotes
                    await ws.send(
                        json.dumps(
                            {
                                "action": "subscribe",
                                "quotes": sub_syms,
                            }
                        )
                    )

                    async for raw in ws:
                        messages = json.loads(raw)
                        for msg in messages:
                            if msg.get("T") != "q":
                                continue
                            sym = msg.get("S", "")
                            yield CanonicalQuote(
                                symbol=sym,
                                price=float(msg.get("ap", msg.get("bp", 0))),
                                bid=float(msg.get("bp", 0)),
                                ask=float(msg.get("ap", 0)),
                                bid_size=float(msg.get("bs", 0)),
                                ask_size=float(msg.get("as", 0)),
                                timestamp=datetime.fromisoformat(
                                    msg.get("t", datetime.now(UTC).isoformat()).replace(
                                        "Z", "+00:00"
                                    )
                                ),
                                provider=self.name,
                                asset_class=infer_asset_class(sym),
                            )
            except Exception:
                logger.warning("alpaca.stream.reconnect", symbols=sub_syms)
                await asyncio.sleep(5)

    async def search_symbols(self, query: str) -> list[dict]:
        if not self._is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://data.alpaca.markets/v2/assets",
                    params={"search": query, "asset_class": "us_equity", "status": "active"},
                    headers=_alpaca_headers(),
                )
                resp.raise_for_status()
                assets = resp.json()
                return [
                    {
                        "symbol": a["symbol"],
                        "name": a.get("name", ""),
                        "exchange": a.get("exchange", ""),
                        "asset_class": "equity",
                    }
                    for a in assets[:20]
                ]
        except Exception:
            logger.exception("alpaca.search.error")
            return []
