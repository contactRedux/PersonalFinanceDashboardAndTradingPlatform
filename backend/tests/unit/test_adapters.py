"""
Unit tests for external adapters: Polygon options, CoinGecko, Binance, FRED cache.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Polygon options adapter (ST-6) ───────────────────────────────────────────


@pytest.mark.anyio
async def test_polygon_adapter_raises_on_missing_key():
    from app.services.options.polygon import PolygonKeyMissing, PolygonOptionsAdapter  # noqa: PLC0415

    with pytest.raises(PolygonKeyMissing):
        PolygonOptionsAdapter(api_key="")


@pytest.mark.anyio
async def test_polygon_adapter_parses_chain_response():
    """Adapter correctly parses a mock Polygon options chain response."""
    from app.services.options.polygon import PolygonOptionsAdapter  # noqa: PLC0415

    mock_snap = {
        "ticker": {"day": {"c": 150.0}},
    }
    mock_chain = {
        "results": [
            {
                "ticker": "O:AAPL240119C00150000",
                "contract_type": "call",
                "expiration_date": "2025-01-17",
                "strike_price": 150.0,
            }
        ]
    }

    adapter = PolygonOptionsAdapter(api_key="test-key")

    call_count = 0

    async def mock_get(path: str, params=None) -> dict:
        nonlocal call_count
        call_count += 1
        if "snapshot" in path:
            return mock_snap
        return mock_chain

    with patch.object(adapter, "_get", side_effect=mock_get):
        result = await adapter.get_options_chain("AAPL")

    assert result["underlying_price"] == 150.0
    assert len(result["contracts"]) == 1
    assert result["contracts"][0]["contract_type"] == "call"
    assert "greeks" in result["contracts"][0]


@pytest.mark.anyio
async def test_polygon_adapter_empty_on_api_error():
    """Adapter returns empty structure when API call fails."""
    from app.services.options.polygon import PolygonError, PolygonOptionsAdapter  # noqa: PLC0415

    adapter = PolygonOptionsAdapter(api_key="test-key")

    with patch.object(adapter, "_get", side_effect=PolygonError("connection error")):
        result = await adapter.get_options_chain("AAPL")

    assert result["contracts"] == []
    assert result["expirations"] == []


# ─── CoinGecko adapter (ST-7) ─────────────────────────────────────────────────


@pytest.mark.anyio
async def test_coingecko_get_coin_stats_parses_response():
    from app.services.crypto.coingecko import CoinGeckoAdapter  # noqa: PLC0415

    mock_data = {
        "symbol": "btc",
        "name": "Bitcoin",
        "market_data": {
            "current_price": {"usd": 45000.0},
            "market_cap": {"usd": 900_000_000_000},
            "total_volume": {"usd": 30_000_000_000},
            "price_change_percentage_24h": 2.5,
            "price_change_24h": 1125.0,
            "circulating_supply": 19_000_000.0,
            "ath": {"usd": 69000.0},
        },
    }
    adapter = CoinGeckoAdapter()

    with patch.object(adapter, "_get", return_value=mock_data):
        result = await adapter.get_coin_stats("bitcoin")

    assert result is not None
    assert result["price"] == 45000.0
    assert result["symbol"] == "BTC"
    assert result["change_pct_24h"] == 2.5


@pytest.mark.anyio
async def test_coingecko_returns_none_on_network_error():
    from app.services.crypto.coingecko import CoinGeckoAdapter  # noqa: PLC0415

    adapter = CoinGeckoAdapter()
    with patch.object(adapter, "_get", return_value=None):
        result = await adapter.get_coin_stats("bitcoin")
    assert result is None


@pytest.mark.anyio
async def test_coingecko_token_bucket_limits_rate():
    """Token bucket depletes and enforces rate limit."""
    import time  # noqa: PLC0415

    from app.services.crypto.coingecko import _TokenBucket  # noqa: PLC0415

    bucket = _TokenBucket(capacity=2.0, refill_rate=100.0)  # fast refill for test
    start = time.monotonic()
    for _ in range(2):
        await bucket.acquire()
    elapsed = time.monotonic() - start
    # Should complete nearly instantly for 2 tokens with capacity=2
    assert elapsed < 1.0


# ─── Binance adapter (ST-8) ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_binance_get_order_book_parses_response():
    from app.services.crypto.binance import BinanceAdapter  # noqa: PLC0415

    mock_data = {
        "lastUpdateId": 12345,
        "bids": [["43000.00", "0.5"], ["42999.00", "1.0"]],
        "asks": [["43001.00", "0.3"], ["43002.00", "0.7"]],
    }
    adapter = BinanceAdapter()
    with patch.object(adapter, "_get", return_value=mock_data):
        result = await adapter.get_order_book("BTCUSDT", limit=20)

    assert len(result["bids"]) == 2
    assert len(result["asks"]) == 2
    assert result["bids"][0][0] == 43000.0


@pytest.mark.anyio
async def test_binance_returns_empty_on_timeout():
    from app.services.crypto.binance import BinanceAdapter  # noqa: PLC0415

    adapter = BinanceAdapter()
    with patch.object(adapter, "_get", return_value=None):
        result = await adapter.get_order_book("BTCUSDT")
    assert result == {"bids": [], "asks": []}


# ─── FRED Redis cache (ST-9) ──────────────────────────────────────────────────


@pytest.mark.anyio
async def test_fred_cache_hit_skips_http_call():
    """If Redis has a cached value, no HTTP request is made."""
    with patch("app.services.macro.fred._cache_get", return_value="5.25"):
        with patch("httpx.AsyncClient") as mock_client:
            from app.services.macro.fred import fetch_series_latest  # noqa: PLC0415

            # Patch settings to provide a key
            with patch("app.services.macro.fred.settings") as mock_settings:
                mock_settings.fred_api_key = "fake-key"
                result = await fetch_series_latest("DFF")

    assert result == 5.25
    mock_client.assert_not_called()


@pytest.mark.anyio
async def test_fred_cache_miss_fetches_and_stores():
    """On cache miss: fetch from FRED, store in Redis."""
    import httpx  # noqa: PLC0415

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "observations": [{"date": "2025-01-01", "value": "4.33"}]
    }

    mock_cache_get = AsyncMock(return_value=None)
    mock_cache_set = AsyncMock()

    with (
        patch("app.services.macro.fred._cache_get", mock_cache_get),
        patch("app.services.macro.fred._cache_set", mock_cache_set),
        patch("httpx.AsyncClient") as mock_http_class,
        patch("app.services.macro.fred.settings") as mock_settings,
    ):
        mock_settings.fred_api_key = "fake-key"
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http_class.return_value = mock_http

        from app.services.macro.fred import fetch_series_latest  # noqa: PLC0415

        result = await fetch_series_latest("DFF")

    assert result == 4.33
    mock_cache_set.assert_called_once()
