"""
Canonical market data schemas.

All market data providers normalize their output to these dataclasses
before anything is written to TimescaleDB or published to Redis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CanonicalBar:
    """Normalized OHLCV bar — all providers produce this shape."""
    time: datetime
    symbol: str
    exchange: str
    asset_class: str          # equity | crypto | forex | futures | options
    timeframe: str            # 1m | 5m | 15m | 1h | 4h | 1d | 1w
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    trade_count: int | None = None
    provider: str = "unknown"


@dataclass
class CanonicalQuote:
    """Normalized real-time quote."""
    symbol: str
    price: float
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    volume: float | None = None
    change: float | None = None
    change_pct: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provider: str = "unknown"
    asset_class: str = "equity"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "change": self.change,
            "change_pct": self.change_pct,
            "timestamp": self.timestamp.isoformat(),
            "provider": self.provider,
            "asset_class": self.asset_class,
        }


def infer_asset_class(symbol: str) -> str:
    """Heuristic asset class detection from symbol format."""
    s = symbol.upper()
    if "-USD" in s or "USDT" in s or "BTC" in s or "ETH" in s:
        return "crypto"
    if "/" in s or len(s) == 6 and s[:3].isalpha() and s[3:].isalpha():
        return "forex"
    return "equity"
