"""
Unit tests for the FMP adapter.
Tests use mocked httpx responses — no real API key needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_mock_client(json_return, status_code: int = 200):
    """Build an async httpx.AsyncClient mock that returns a given JSON payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_return

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


# ─── get_profile ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_profile_returns_dict_when_mocked():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    fake = [{"companyName": "Apple Inc.", "sector": "Technology", "mktCap": 3e12}]
    mock_client = _make_mock_client(fake)

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
        patch("app.services.fundamentals.fmp._cache_set"),
    ):
        result = await fmp_mod.get_profile("AAPL")

    assert result is not None
    assert result["companyName"] == "Apple Inc."
    assert result["sector"] == "Technology"


@pytest.mark.anyio
async def test_get_profile_returns_none_when_no_key():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    with patch.object(fmp_mod.settings, "fmp_api_key", ""):
        result = await fmp_mod.get_profile("AAPL")

    assert result is None


# ─── get_income_statement ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_income_statement_returns_list():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    fake = [{"date": "2024-09-28", "revenue": 391_035_000_000, "netIncome": 93_736_000_000}]
    mock_client = _make_mock_client(fake)

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
        patch("app.services.fundamentals.fmp._cache_set"),
    ):
        result = await fmp_mod.get_income_statement("AAPL")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["revenue"] == 391_035_000_000


# ─── get_dcf ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_dcf_returns_dict():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    fake = {"symbol": "AAPL", "dcf": 195.42, "Stock Price": 182.30}
    mock_client = _make_mock_client(fake)

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
        patch("app.services.fundamentals.fmp._cache_set"),
    ):
        result = await fmp_mod.get_dcf("AAPL")

    assert result is not None
    assert result["dcf"] == 195.42


# ─── get_insider_transactions ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_insider_transactions_returns_list():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    fake = [
        {
            "symbol": "AAPL",
            "transactionDate": "2024-11-01",
            "reportingName": "Tim Cook",
            "typeOfOwner": "CEO",
            "transactionType": "S-Sale",
            "securitiesTransacted": 5000.0,
            "price": 222.91,
        }
    ]
    mock_client = _make_mock_client(fake)

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
        patch("app.services.fundamentals.fmp._cache_set"),
    ):
        result = await fmp_mod.get_insider_transactions("AAPL")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["reportingName"] == "Tim Cook"


# ─── HTTP error handling ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_adapter_returns_none_on_http_error():
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    mock_client = _make_mock_client({}, status_code=429)

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
    ):
        result = await fmp_mod.get_profile("AAPL")

    assert result is None


@pytest.mark.anyio
async def test_adapter_returns_none_on_network_error():
    import httpx  # noqa: PLC0415
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    with (
        patch("app.services.fundamentals.fmp.httpx.AsyncClient", return_value=mock_client),
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=None),
    ):
        result = await fmp_mod.get_profile("AAPL")

    assert result is None


# ─── Redis cache hit ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_profile_uses_cache():
    """When Redis has a cached response, no HTTP call is made."""
    import json  # noqa: PLC0415
    import app.services.fundamentals.fmp as fmp_mod  # noqa: PLC0415

    cached_data = json.dumps([{"companyName": "Apple Inc.", "sector": "Technology"}])

    with (
        patch.object(fmp_mod.settings, "fmp_api_key", "test_key"),
        patch("app.services.fundamentals.fmp._cache_get", return_value=cached_data),
        patch("app.services.fundamentals.fmp.httpx.AsyncClient") as mock_http,
    ):
        result = await fmp_mod.get_profile("AAPL")

    # HTTP client should never be called when cache is warm
    mock_http.assert_not_called()
    assert result is not None
    assert result["companyName"] == "Apple Inc."


# ─── build_demo_fundamentals ──────────────────────────────────────────────────

def test_build_demo_fundamentals_has_required_keys():
    from app.services.fundamentals.fmp import build_demo_fundamentals  # noqa: PLC0415

    result = build_demo_fundamentals("AAPL")
    assert result["symbol"] == "AAPL"
    assert "profile" in result
    assert "income_statement" in result
    assert "balance_sheet" in result
    assert "cash_flow" in result
    assert "key_metrics" in result
    assert "dcf" in result
    assert "earnings_history" in result
    assert "analyst_estimates" in result
    assert "insider_transactions" in result
    assert "institutional_holders" in result
    assert "note" in result
