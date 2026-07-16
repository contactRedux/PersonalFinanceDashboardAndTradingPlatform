"""
Unit tests for OpenInsider, StockTwits, and EarningsCall.ai adapters.
All tests use mocked HTTP responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── OpenInsider Adapter ──────────────────────────────────────────────────────

SAMPLE_OPENINSIDER_HTML = """
<html><body>
<table class="tinytable">
<thead><tr><th>Filing Date</th><th>Trade Date</th><th>Ticker</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th>
<th>Price</th><th>Qty</th><th>Owned</th><th>%Chg</th><th>Value</th></tr></thead>
<tbody>
<tr>
  <td>2024-11-01</td><td>2024-10-30</td><td>AAPL</td>
  <td>Tim Cook</td><td>CEO</td><td>S - Sale</td>
  <td>$222.91</td><td>5,000</td><td>3,280,000</td><td>0.15%</td><td>$1,114,550</td>
</tr>
<tr>
  <td>2024-10-15</td><td>2024-10-14</td><td>AAPL</td>
  <td>Luca Maestri</td><td>CFO</td><td>P - Purchase</td>
  <td>$220.00</td><td>1,000</td><td>500,000</td><td>0.20%</td><td>$220,000</td>
</tr>
</tbody>
</table>
</body></html>
"""


def test_openinsider_parses_rows_correctly():
    """Test the HTML table parser directly (pure sync method)."""
    from app.services.news.openinsider import OpenInsiderAdapter  # noqa: PLC0415

    adapter = OpenInsiderAdapter()
    results = adapter._parse_html_table(SAMPLE_OPENINSIDER_HTML, "AAPL")

    assert isinstance(results, list)
    assert len(results) == 2

    ceo_tx = next(r for r in results if r["insider_name"] == "Tim Cook")
    cfo_tx = next(r for r in results if r["insider_name"] == "Luca Maestri")

    assert ceo_tx["transaction_type"] == "S"
    assert cfo_tx["transaction_type"] == "P"
    assert ceo_tx["shares"] == 5000.0
    assert ceo_tx["price"] == 222.91
    assert ceo_tx["source"] == "openinsider"


@pytest.mark.anyio
async def test_openinsider_returns_empty_on_http_error():
    from app.services.news.openinsider import OpenInsiderAdapter  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = ""

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = OpenInsiderAdapter()
    with (
        patch("app.services.news.openinsider.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.openinsider._cache_get", return_value=None),
    ):
        results = await adapter.get_recent_trades("AAPL")

    assert results == []


@pytest.mark.anyio
async def test_openinsider_uses_cache():
    """When Redis has a cached response, no HTTP call is made."""
    import json  # noqa: PLC0415
    from app.services.news.openinsider import OpenInsiderAdapter  # noqa: PLC0415

    cached = json.dumps([{"symbol": "AAPL", "insider_name": "Tim Cook", "source": "openinsider"}])
    adapter = OpenInsiderAdapter()

    with (
        patch("app.services.news.openinsider._cache_get", return_value=cached),
        patch("app.services.news.openinsider.httpx.AsyncClient") as mock_http,
    ):
        results = await adapter.get_recent_trades("AAPL")

    mock_http.assert_not_called()
    assert len(results) == 1
    assert results[0]["insider_name"] == "Tim Cook"


def test_openinsider_within_days_filter():
    from app.services.news.openinsider import OpenInsiderAdapter  # noqa: PLC0415
    from datetime import date, timedelta  # noqa: PLC0415

    adapter = OpenInsiderAdapter()
    today_str = date.today().isoformat()
    old_date_str = (date.today() - timedelta(days=200)).isoformat()

    assert adapter._within_days(today_str, 90) is True
    assert adapter._within_days(old_date_str, 90) is False
    assert adapter._within_days("", 90) is True  # missing date = include


# ─── StockTwits Adapter ───────────────────────────────────────────────────────

SAMPLE_STOCKTWITS_RESPONSE = {
    "symbol": {"symbol": "AAPL", "title": "Apple Inc."},
    "messages": [
        {
            "body": "$AAPL looks very bullish today!",
            "created_at": "2024-11-01T10:00:00Z",
            "user": {"username": "trader123"},
            "likes": {"total": 5},
            "entities": {"sentiment": {"basic": "Bullish"}},
        },
        {
            "body": "$AAPL might pull back here",
            "created_at": "2024-11-01T09:30:00Z",
            "user": {"username": "analyst456"},
            "likes": {"total": 2},
            "entities": {"sentiment": {"basic": "Bearish"}},
        },
        {
            "body": "Watching $AAPL",
            "created_at": "2024-11-01T09:00:00Z",
            "user": {"username": "watcher789"},
            "likes": {"total": 0},
            "entities": {},  # no sentiment tag
        },
    ],
}


@pytest.mark.anyio
async def test_stocktwits_returns_stream_with_bullish_pct():
    import app.services.news.stocktwits as st_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_STOCKTWITS_RESPONSE

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = st_mod.StockTwitsAdapter()
    with (
        patch("app.services.news.stocktwits.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.stocktwits._cache_get", return_value=None),
        patch("app.services.news.stocktwits._cache_set"),
        patch.object(st_mod.settings, "stocktwits_access_token", ""),
    ):
        result = await adapter.get_stream("AAPL")

    assert result["symbol"] == "AAPL"
    assert len(result["messages"]) == 3
    assert result["bullish_count"] == 1
    assert result["bearish_count"] == 1
    # 1 bullish / (1 bull + 1 bear) = 0.5
    assert result["bullish_pct"] == 0.5
    assert result["tagged_count"] == 2


@pytest.mark.anyio
async def test_stocktwits_graceful_on_rate_limit():
    import app.services.news.stocktwits as st_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = st_mod.StockTwitsAdapter()
    with (
        patch("app.services.news.stocktwits.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.stocktwits._cache_get", return_value=None),
        patch("app.services.news.stocktwits._cache_set"),
        patch.object(st_mod.settings, "stocktwits_access_token", ""),
    ):
        result = await adapter.get_stream("AAPL")

    assert result["messages"] == []
    assert result["bullish_pct"] == 0.5  # neutral fallback


@pytest.mark.anyio
async def test_stocktwits_uses_cache():
    import json  # noqa: PLC0415
    from app.services.news.stocktwits import StockTwitsAdapter  # noqa: PLC0415

    cached = json.dumps({"symbol": "AAPL", "messages": [], "bullish_pct": 0.7, "message_count": 0})

    adapter = StockTwitsAdapter()
    with (
        patch("app.services.news.stocktwits._cache_get", return_value=cached),
        patch("app.services.news.stocktwits.httpx.AsyncClient") as mock_http,
    ):
        result = await adapter.get_stream("AAPL")

    mock_http.assert_not_called()
    assert result["bullish_pct"] == 0.7


# ─── EarningsCall.ai Adapter ──────────────────────────────────────────────────

SAMPLE_EARNINGSCALL_EVENTS = [
    {"year": 2024, "quarter": 4, "conferenceDate": "2024-10-31", "hasTranscript": True},
    {"year": 2024, "quarter": 3, "conferenceDate": "2024-08-01", "hasTranscript": True},
]

SAMPLE_EARNINGSCALL_TRANSCRIPT = {
    "text": "Good afternoon. Tim Cook here...",
    "speakers": ["Tim Cook", "Luca Maestri"],
    "conferenceDate": "2024-10-31",
}


@pytest.mark.anyio
async def test_earningscall_returns_events_list():
    import app.services.news.earningscall as ec_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_EARNINGSCALL_EVENTS

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = ec_mod.EarningsCallAdapter()
    with (
        patch("app.services.news.earningscall.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.earningscall._cache_get", return_value=None),
        patch("app.services.news.earningscall._cache_set"),
        patch.object(ec_mod.settings, "earningscall_api_key", "test_key"),
    ):
        results = await adapter.get_recent_transcripts("AAPL", limit=4)

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["year"] == 2024
    assert results[0]["quarter"] == 4
    assert results[0]["source"] == "earningscall"


@pytest.mark.anyio
async def test_earningscall_returns_empty_without_key():
    import app.services.news.earningscall as ec_mod  # noqa: PLC0415

    adapter = ec_mod.EarningsCallAdapter()
    with patch.object(ec_mod.settings, "earningscall_api_key", ""):
        results = await adapter.get_recent_transcripts("AAPL")

    assert results == []


@pytest.mark.anyio
async def test_earningscall_returns_none_for_missing_transcript():
    import app.services.news.earningscall as ec_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = ec_mod.EarningsCallAdapter()
    with (
        patch("app.services.news.earningscall.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.earningscall._cache_get", return_value=None),
        patch.object(ec_mod.settings, "earningscall_api_key", "test_key"),
    ):
        result = await adapter.get_transcript("AAPL", year=2020, quarter=1)

    assert result is None


@pytest.mark.anyio
async def test_earningscall_transcript_has_correct_keys():
    import app.services.news.earningscall as ec_mod  # noqa: PLC0415

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_EARNINGSCALL_TRANSCRIPT

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = ec_mod.EarningsCallAdapter()
    with (
        patch("app.services.news.earningscall.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.news.earningscall._cache_get", return_value=None),
        patch("app.services.news.earningscall._cache_set"),
        patch.object(ec_mod.settings, "earningscall_api_key", "test_key"),
    ):
        result = await adapter.get_transcript("AAPL", year=2024, quarter=4)

    assert result is not None
    assert result["symbol"] == "AAPL"
    assert result["year"] == 2024
    assert result["quarter"] == 4
    assert "text" in result
    assert result["source"] == "earningscall"
