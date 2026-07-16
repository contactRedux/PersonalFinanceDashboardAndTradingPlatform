"""
Unit tests for the OpenFIGI adapter.
All tests use mocked HTTP responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


SAMPLE_OPENFIGI_RESPONSE = [
    {
        "data": [
            {
                "figi": "BBG000B9Y5X2",
                "isin": "US0378331005",
                "cusip": "037833100",
                "sedol": "2046251",
                "name": "APPLE INC",
                "ticker": "AAPL",
                "exchCode": "US",
                "securityType": "Common Stock",
                "securityType2": "Common Stock",
                "marketSector": "Equity",
            }
        ]
    }
]


# ─── OpenFIGIAdapter.map_identifiers ─────────────────────────────────────────

@pytest.mark.anyio
async def test_openfigi_returns_identifiers():
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENFIGI_RESPONSE

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = OpenFIGIAdapter()
    with (
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=None),
        patch("app.services.fundamentals.openfigi._cache_set", new_callable=AsyncMock),
        patch.object(figi_mod.settings, "openfigi_api_key", ""),
    ):
        result = await adapter.map_identifiers("AAPL", exchange="US")

    assert result["figi"] == "BBG000B9Y5X2"
    assert result["isin"] == "US0378331005"
    assert result["cusip"] == "037833100"
    assert result["sedol"] == "2046251"
    assert result["name"] == "APPLE INC"
    assert result["source"] == "openfigi"
    assert result["ticker"] == "AAPL"


@pytest.mark.anyio
async def test_openfigi_includes_api_key_header_when_configured():
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENFIGI_RESPONSE

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = OpenFIGIAdapter()
    with (
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=None),
        patch("app.services.fundamentals.openfigi._cache_set", new_callable=AsyncMock),
        patch.object(figi_mod.settings, "openfigi_api_key", "my-figi-key"),
    ):
        await adapter.map_identifiers("AAPL")

    # Check that the API key header was passed
    call_kwargs = mock_client.post.call_args.kwargs
    headers = call_kwargs.get("headers", {})
    assert "X-OPENFIGI-APIKEY" in headers
    assert headers["X-OPENFIGI-APIKEY"] == "my-figi-key"


@pytest.mark.anyio
async def test_openfigi_no_api_key_header_when_empty():
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENFIGI_RESPONSE

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = OpenFIGIAdapter()
    with (
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=None),
        patch("app.services.fundamentals.openfigi._cache_set", new_callable=AsyncMock),
        patch.object(figi_mod.settings, "openfigi_api_key", ""),
    ):
        await adapter.map_identifiers("AAPL")

    call_kwargs = mock_client.post.call_args.kwargs
    headers = call_kwargs.get("headers", {})
    assert "X-OPENFIGI-APIKEY" not in headers


@pytest.mark.anyio
async def test_openfigi_returns_empty_on_rate_limit():
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = OpenFIGIAdapter()
    with (
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=None),
        patch("app.services.fundamentals.openfigi._cache_set", new_callable=AsyncMock),
        patch.object(figi_mod.settings, "openfigi_api_key", ""),
    ):
        result = await adapter.map_identifiers("AAPL")

    assert result == {}


@pytest.mark.anyio
async def test_openfigi_returns_empty_on_no_data():
    """When OpenFIGI returns an empty data list for the ticker, return {}."""
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"data": []}]

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = OpenFIGIAdapter()
    with (
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=None),
        patch("app.services.fundamentals.openfigi._cache_set", new_callable=AsyncMock),
        patch.object(figi_mod.settings, "openfigi_api_key", ""),
    ):
        result = await adapter.map_identifiers("UNKNOWN_TICKER")

    assert result == {}


@pytest.mark.anyio
async def test_openfigi_uses_cache():
    import json  # noqa: PLC0415
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415
    import app.services.fundamentals.openfigi as figi_mod  # noqa: PLC0415

    cached = json.dumps({
        "figi": "BBG000B9Y5X2",
        "isin": "US0378331005",
        "cusip": "037833100",
        "source": "openfigi",
        "ticker": "AAPL",
    })

    adapter = OpenFIGIAdapter()
    with (
        patch.object(figi_mod.settings, "openfigi_api_key", ""),
        patch("app.services.fundamentals.openfigi._cache_get", return_value=cached),
        patch("app.services.fundamentals.openfigi.httpx.AsyncClient") as mock_http,
    ):
        result = await adapter.map_identifiers("AAPL")

    mock_http.assert_not_called()
    assert result["figi"] == "BBG000B9Y5X2"


@pytest.mark.anyio
async def test_openfigi_enrich_search_results():
    """enrich_search_results() adds identifier fields to each result dict."""
    from app.services.fundamentals.openfigi import OpenFIGIAdapter  # noqa: PLC0415

    identifiers = {
        "figi": "BBG000B9Y5X2",
        "isin": "US0378331005",
        "cusip": "037833100",
        "sedol": "2046251",
        "source": "openfigi",
        "ticker": "AAPL",
    }

    results = [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "US", "asset_class": "equity"},
        {"symbol": "AAPL1", "name": "Apple Warrant", "exchange": "US", "asset_class": "equity"},
    ]

    adapter = OpenFIGIAdapter()
    with patch.object(adapter, "map_identifiers", new=AsyncMock(return_value=identifiers)):
        enriched = await adapter.enrich_search_results(results)

    for item in enriched:
        assert item.get("figi") == "BBG000B9Y5X2"
        assert item.get("isin") == "US0378331005"
        assert item.get("cusip") == "037833100"
