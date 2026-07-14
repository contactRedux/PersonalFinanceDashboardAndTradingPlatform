"""
Abstract base class for all market data providers.

Every provider must implement:
  - get_bars()    — historical OHLCV bars
  - get_quote()   — latest quote for a symbol
  - get_quotes()  — batch quotes
  - stream_quotes() — async generator of real-time quote updates

All methods return data in the canonical schema defined in normalizer.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.data.ingestion.normalizer import CanonicalBar, CanonicalQuote


class MarketDataProvider(ABC):
    """Abstract market data provider interface."""

    name: str = "base"

    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 500,
    ) -> list[CanonicalBar]:
        """Return historical OHLCV bars for a symbol."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> CanonicalQuote | None:
        """Return the latest quote for a symbol."""

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> dict[str, CanonicalQuote | None]:
        """Return latest quotes for multiple symbols (batch)."""

    @abstractmethod
    async def stream_quotes(self, symbols: list[str]) -> AsyncGenerator[CanonicalQuote, None]:
        """
        Async generator — yields real-time quote updates for subscribed symbols.
        Should reconnect automatically on network errors.
        """
        # Required for type checking; abstract generators must have a yield
        raise NotImplementedError
        yield  # type: ignore[misc]

    async def search_symbols(self, query: str) -> list[dict]:
        """Optional symbol search — not all providers support it."""
        return []
