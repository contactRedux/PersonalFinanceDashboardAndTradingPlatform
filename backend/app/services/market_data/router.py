"""
Market data provider router — priority-based selection with fallback.

Priority order (configurable via MARKET_DATA_PROVIDER env var):
  1. alpaca  — best real-time streaming (requires API key)
  2. yfinance — free polling fallback (always available)

Usage:
    from app.services.market_data.router import get_provider
    provider = get_provider()
    bars = await provider.get_bars("AAPL", "1d")
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.services.market_data.alpaca import AlpacaProvider
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.yahoo_finance import YFinanceProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_providers: dict[str, MarketDataProvider] = {
    "alpaca": AlpacaProvider(),
    "yfinance": YFinanceProvider(),
}

_priority = ["alpaca", "yfinance"]


def get_provider(name: str | None = None) -> MarketDataProvider:
    """
    Return the configured provider. Falls back down the priority list if
    the requested provider is not available (missing API keys).
    """
    preferred = name or settings.market_data_provider or "alpaca"

    if preferred in _providers:
        provider = _providers[preferred]
        # Check if alpaca is actually configured
        if preferred == "alpaca" and not (settings.alpaca_api_key and settings.alpaca_api_secret):
            logger.warning(
                "market_data.provider.fallback",
                requested=preferred,
                fallback="yfinance",
                reason="Alpaca API keys not configured",
            )
            return _providers["yfinance"]
        return provider

    # Unknown provider — use default priority order
    for p_name in _priority:
        p = _providers[p_name]
        if p_name == "alpaca" and not (settings.alpaca_api_key and settings.alpaca_api_secret):
            continue
        logger.info("market_data.provider.selected", provider=p_name)
        return p

    return _providers["yfinance"]


def get_all_providers() -> list[MarketDataProvider]:
    """Return all configured providers (for multi-source aggregation)."""
    return list(_providers.values())
