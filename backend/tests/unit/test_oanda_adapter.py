"""
Unit tests for the OANDA forex provider.
All tests use mocked HTTP responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── OANDA symbol normalisation ───────────────────────────────────────────────

def test_normalise_symbol_slash():
    from app.services.market_data.oanda import _normalise_symbol  # noqa: PLC0415
    assert _normalise_symbol("EUR/USD") == "EUR_USD"


def test_normalise_symbol_no_delimiter():
    from app.services.market_data.oanda import _normalise_symbol  # noqa: PLC0415
    assert _normalise_symbol("EURUSD") == "EUR_USD"


def test_normalise_symbol_already_oanda_format():
    from app.services.market_data.oanda import _normalise_symbol  # noqa: PLC0415
    assert _normalise_symbol("EUR_USD") == "EUR_USD"


# ─── OANDAProvider ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_oanda_get_bars_returns_empty_when_not_configured():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    provider = OANDAProvider()
    with (
        patch.object(oanda_mod.settings, "oanda_api_key", ""),
        patch.object(oanda_mod.settings, "oanda_account_id", ""),
    ):
        result = await provider.get_bars("EUR_USD", "1h")

    assert result == []


@pytest.mark.anyio
async def test_oanda_get_bars_returns_canonical_bars():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    mock_response = {
        "candles": [
            {
                "time": "2024-11-01T10:00:00.000000000Z",
                "complete": True,
                "volume": 1500,
                "mid": {"o": "1.08200", "h": "1.08350", "l": "1.08100", "c": "1.08290"},
            },
            {
                "time": "2024-11-01T11:00:00.000000000Z",
                "complete": True,
                "volume": 1200,
                "mid": {"o": "1.08290", "h": "1.08400", "l": "1.08200", "c": "1.08350"},
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    provider = OANDAProvider()
    with (
        patch("app.services.market_data.oanda.httpx.AsyncClient", return_value=mock_client),
        patch.object(oanda_mod.settings, "oanda_api_key", "test-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(oanda_mod.settings, "oanda_base_url", "https://api-fxpractice.oanda.com"),
    ):
        bars = await provider.get_bars("EUR_USD", "1h")

    assert len(bars) == 2
    assert bars[0].symbol == "EUR_USD"
    assert bars[0].asset_class == "forex"
    assert bars[0].open == pytest.approx(1.082, abs=1e-4)
    assert bars[0].provider == "oanda"


@pytest.mark.anyio
async def test_oanda_get_bars_skips_incomplete_candles():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    mock_response = {
        "candles": [
            {
                "time": "2024-11-01T10:00:00Z",
                "complete": True,
                "volume": 1500,
                "mid": {"o": "1.08200", "h": "1.08350", "l": "1.08100", "c": "1.08290"},
            },
            {
                # incomplete candle — should be skipped
                "time": "2024-11-01T11:00:00Z",
                "complete": False,
                "volume": 100,
                "mid": {"o": "1.08290", "h": "1.08300", "l": "1.08280", "c": "1.08295"},
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    provider = OANDAProvider()
    with (
        patch("app.services.market_data.oanda.httpx.AsyncClient", return_value=mock_client),
        patch.object(oanda_mod.settings, "oanda_api_key", "test-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(oanda_mod.settings, "oanda_base_url", "https://api-fxpractice.oanda.com"),
    ):
        bars = await provider.get_bars("EUR_USD", "1h")

    assert len(bars) == 1


@pytest.mark.anyio
async def test_oanda_get_quotes_returns_canonical_quote():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    mock_response = {
        "prices": [
            {
                "instrument": "EUR_USD",
                "time": "2024-11-01T10:00:00.000000000Z",
                "bids": [{"price": "1.08250", "liquidity": 10000000}],
                "asks": [{"price": "1.08260", "liquidity": 10000000}],
                "status": "tradeable",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    provider = OANDAProvider()
    with (
        patch("app.services.market_data.oanda.httpx.AsyncClient", return_value=mock_client),
        patch.object(oanda_mod.settings, "oanda_api_key", "test-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(oanda_mod.settings, "oanda_base_url", "https://api-fxpractice.oanda.com"),
    ):
        quotes = await provider.get_quotes(["EUR_USD"])

    assert "EUR_USD" in quotes
    q = quotes["EUR_USD"]
    assert q is not None
    assert q.bid == pytest.approx(1.0825)
    assert q.ask == pytest.approx(1.0826)
    assert q.price == pytest.approx((1.0825 + 1.0826) / 2)
    assert q.asset_class == "forex"
    assert q.provider == "oanda"


@pytest.mark.anyio
async def test_oanda_get_quote_delegates_to_get_quotes():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415
    from unittest.mock import AsyncMock  # noqa: PLC0415
    from app.data.ingestion.normalizer import CanonicalQuote  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    mock_quote = CanonicalQuote(
        symbol="EUR_USD",
        price=1.0825,
        bid=1.0824,
        ask=1.0826,
        bid_size=0,
        ask_size=0,
        timestamp=datetime.now(UTC),
        provider="oanda",
        asset_class="forex",
    )

    provider = OANDAProvider()
    with (
        patch.object(oanda_mod.settings, "oanda_api_key", "test-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(provider, "get_quotes", new=AsyncMock(return_value={"EUR_USD": mock_quote})),
    ):
        result = await provider.get_quote("EUR_USD")

    assert result is not None
    assert result.price == pytest.approx(1.0825)


@pytest.mark.anyio
async def test_oanda_search_symbols():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    mock_response = {
        "instruments": [
            {"name": "EUR_USD", "displayName": "EUR/USD", "type": "CURRENCY"},
            {"name": "EUR_GBP", "displayName": "EUR/GBP", "type": "CURRENCY"},
            {"name": "USD_JPY", "displayName": "USD/JPY", "type": "CURRENCY"},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    provider = OANDAProvider()
    with (
        patch("app.services.market_data.oanda.httpx.AsyncClient", return_value=mock_client),
        patch.object(oanda_mod.settings, "oanda_api_key", "test-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(oanda_mod.settings, "oanda_base_url", "https://api-fxpractice.oanda.com"),
    ):
        results = await provider.search_symbols("EUR")

    # EUR_USD and EUR_GBP match "EUR"
    assert len(results) >= 2
    symbols = [r["symbol"] for r in results]
    assert "EUR_USD" in symbols
    assert "EUR_GBP" in symbols
    assert all(r["asset_class"] == "forex" for r in results)


@pytest.mark.anyio
async def test_oanda_returns_empty_on_http_error():
    from app.services.market_data.oanda import OANDAProvider  # noqa: PLC0415
    import app.services.market_data.oanda as oanda_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 401 Unauthorized")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    provider = OANDAProvider()
    with (
        patch("app.services.market_data.oanda.httpx.AsyncClient", return_value=mock_client),
        patch.object(oanda_mod.settings, "oanda_api_key", "bad-key"),
        patch.object(oanda_mod.settings, "oanda_account_id", "001-001-12345-001"),
        patch.object(oanda_mod.settings, "oanda_base_url", "https://api-fxpractice.oanda.com"),
    ):
        bars = await provider.get_bars("EUR_USD", "1h")

    assert bars == []
