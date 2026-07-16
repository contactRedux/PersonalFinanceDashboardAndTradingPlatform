"""
Unit tests for the FactSet adapter.
All tests use mocked HTTP responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── FactSet auth helper ──────────────────────────────────────────────────────

def test_factset_auth_returns_none_when_not_configured():
    from app.services.fundamentals.factset import _factset_auth  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    with patch.object(fs_mod.settings, "factset_api_key", ""):
        assert _factset_auth() is None


def test_factset_auth_returns_none_for_malformed_key():
    from app.services.fundamentals.factset import _factset_auth  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    with patch.object(fs_mod.settings, "factset_api_key", "nocolon"):
        assert _factset_auth() is None


def test_factset_auth_parses_valid_key():
    from app.services.fundamentals.factset import _factset_auth  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    with patch.object(fs_mod.settings, "factset_api_key", "user@company.com:myapikey"):
        result = _factset_auth()

    assert result is not None
    assert result == ("user@company.com", "myapikey")


# ─── FactSetAdapter.get_profile ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_factset_get_profile_returns_empty_when_not_configured():
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    adapter = FactSetAdapter()
    with patch.object(fs_mod.settings, "factset_api_key", ""):
        result = await adapter.get_profile("AAPL")

    assert result == {}


@pytest.mark.anyio
async def test_factset_get_profile_returns_profile_data():
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    mock_response = {
        "data": {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "description": "Apple designs, manufactures, and markets smartphones.",
            "exchange": "NASDAQ",
            "country": "US",
            "factsetId": "0016YD-E",
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = FactSetAdapter()
    with (
        patch("app.services.fundamentals.factset.httpx.AsyncClient", return_value=mock_client),
        patch.object(fs_mod.settings, "factset_api_key", "user@co.com:apikey123"),
        patch("app.services.fundamentals.factset._cache_get", return_value=None),
        patch("app.services.fundamentals.factset._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_profile("AAPL")

    assert result["name"] == "Apple Inc."
    assert result["sector"] == "Technology"
    assert result["source"] == "factset"
    assert result["symbol"] == "AAPL"


@pytest.mark.anyio
async def test_factset_get_profile_returns_empty_on_404():
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = FactSetAdapter()
    with (
        patch("app.services.fundamentals.factset.httpx.AsyncClient", return_value=mock_client),
        patch.object(fs_mod.settings, "factset_api_key", "user@co.com:apikey123"),
        patch("app.services.fundamentals.factset._cache_get", return_value=None),
    ):
        result = await adapter.get_profile("UNKNOWN_TICKER")

    assert result == {}


@pytest.mark.anyio
async def test_factset_get_profile_uses_cache():
    import json  # noqa: PLC0415
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    cached = json.dumps({
        "symbol": "AAPL",
        "name": "Apple Inc. (cached)",
        "source": "factset",
    })

    adapter = FactSetAdapter()
    with (
        patch.object(fs_mod.settings, "factset_api_key", "user@co.com:apikey123"),
        patch("app.services.fundamentals.factset._cache_get", return_value=cached),
        patch("app.services.fundamentals.factset.httpx.AsyncClient") as mock_http,
    ):
        result = await adapter.get_profile("AAPL")

    mock_http.assert_not_called()
    assert result["name"] == "Apple Inc. (cached)"


# ─── FactSetAdapter.get_financials ────────────────────────────────────────────

@pytest.mark.anyio
async def test_factset_get_financials_returns_structured_data():
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    mock_response = {
        "data": {
            "incomeStatement": [{"year": 2024, "revenue": 391035000000}],
            "balanceSheet": [{"year": 2024, "totalAssets": 352583000000}],
            "cashFlowStatement": [{"year": 2024, "operatingCashFlow": 113000000000}],
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = FactSetAdapter()
    with (
        patch("app.services.fundamentals.factset.httpx.AsyncClient", return_value=mock_client),
        patch.object(fs_mod.settings, "factset_api_key", "user@co.com:apikey123"),
        patch("app.services.fundamentals.factset._cache_get", return_value=None),
        patch("app.services.fundamentals.factset._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_financials("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["source"] == "factset"
    assert len(result["income"]) == 1
    assert result["income"][0]["revenue"] == 391035000000


# ─── FactSetAdapter.get_estimates ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_factset_get_estimates_returns_consensus():
    from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
    import app.services.fundamentals.factset as fs_mod  # noqa: PLC0415

    mock_response = {
        "data": [
            {"id": "AAPL-US", "metric": "EPS", "fiscalPeriod": "0FY", "value": 6.72},
            {"id": "AAPL-US", "metric": "SALES", "fiscalPeriod": "0FY", "value": 395000000000},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    adapter = FactSetAdapter()
    with (
        patch("app.services.fundamentals.factset.httpx.AsyncClient", return_value=mock_client),
        patch.object(fs_mod.settings, "factset_api_key", "user@co.com:apikey123"),
        patch("app.services.fundamentals.factset._cache_get", return_value=None),
        patch("app.services.fundamentals.factset._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_estimates("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["source"] == "factset"
    assert len(result["consensus"]) == 2
