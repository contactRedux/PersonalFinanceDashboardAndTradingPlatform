"""
Unit tests for the Refinitiv adapter.
All tests run without a real Refinitiv license or SDK — the SDK is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Refinitiv Adapter ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_refinitiv_returns_empty_when_no_app_key():
    """Without REFINITIV_APP_KEY, get_news() returns empty list immediately."""
    import app.services.news.refinitiv as ref_mod  # noqa: PLC0415

    adapter = ref_mod.RefinitivAdapter()
    with patch.object(ref_mod.settings, "refinitiv_app_key", ""):
        result = await adapter.get_news("AAPL")

    assert result == []


@pytest.mark.anyio
async def test_refinitiv_returns_empty_when_sdk_not_installed():
    """When refinitiv.data SDK is not installed, get_news() returns empty list."""
    import app.services.news.refinitiv as ref_mod  # noqa: PLC0415

    adapter = ref_mod.RefinitivAdapter()
    with (
        patch.object(ref_mod, "_REFINITIV_SDK_AVAILABLE", False),
        patch.object(ref_mod.settings, "refinitiv_app_key", "test-app-key"),
    ):
        result = await adapter.get_news("AAPL")

    assert result == []


@pytest.mark.anyio
async def test_refinitiv_returns_articles_when_sdk_available():
    """When SDK is 'installed' and key is set, get_news() returns mapped articles."""
    import pandas as pd  # noqa: PLC0415
    import app.services.news.refinitiv as ref_mod  # noqa: PLC0415

    # Build a mock DataFrame that the SDK would return
    mock_df = pd.DataFrame([
        {
            "versionCreated": "2024-11-01T10:00:00+00:00",
            "text": "Apple reports record earnings for Q4",
            "storyId": "urn:newsml:reuters.com:20241101:nL8N3N100A",
            "sourceCode": "RSF",
        },
        {
            "versionCreated": "2024-11-01T09:00:00+00:00",
            "text": "iPhone 16 demand exceeds analyst expectations",
            "storyId": "urn:newsml:reuters.com:20241101:nL8N3N200B",
            "sourceCode": "RSF",
        },
    ])

    mock_rd = MagicMock()
    mock_rd.get_news_headlines.return_value = mock_df
    mock_rd.open_session = MagicMock()
    mock_rd.close_session = MagicMock()

    adapter = ref_mod.RefinitivAdapter()
    with (
        patch.object(ref_mod, "_REFINITIV_SDK_AVAILABLE", True),
        patch.object(ref_mod, "rd", mock_rd),
        patch.object(ref_mod.settings, "refinitiv_app_key", "test-app-key"),
        patch("app.services.news.refinitiv._cache_get", return_value=None),
        patch("app.services.news.refinitiv._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_news("AAPL", limit=10)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["source"] == "refinitiv"
    assert "Apple reports record earnings" in result[0]["headline"]
    assert result[0]["source_id"].startswith("urn:newsml")


@pytest.mark.anyio
async def test_refinitiv_uses_cache():
    """When Redis has a cached result, no SDK call is made."""
    import json  # noqa: PLC0415
    import app.services.news.refinitiv as ref_mod  # noqa: PLC0415

    cached_articles = json.dumps([{
        "headline": "Reuters cached story",
        "source": "refinitiv",
        "source_id": "story-1",
        "url": "https://refinitiv.com/story-1",
        "published_at": "2024-11-01T10:00:00+00:00",
        "tickers_mentioned": ["AAPL"],
    }])

    adapter = ref_mod.RefinitivAdapter()
    mock_rd = MagicMock()

    with (
        patch.object(ref_mod, "_REFINITIV_SDK_AVAILABLE", True),
        patch.object(ref_mod, "rd", mock_rd),
        patch.object(ref_mod.settings, "refinitiv_app_key", "test-app-key"),
        patch("app.services.news.refinitiv._cache_get", return_value=cached_articles),
    ):
        result = await adapter.get_news("AAPL")

    mock_rd.get_news_headlines.assert_not_called()
    assert len(result) == 1
    assert result[0]["headline"] == "Reuters cached story"


@pytest.mark.anyio
async def test_refinitiv_returns_empty_on_sdk_exception():
    """If the SDK raises an exception, get_news() returns [] gracefully."""
    import app.services.news.refinitiv as ref_mod  # noqa: PLC0415

    mock_rd = MagicMock()
    mock_rd.open_session.side_effect = RuntimeError("SDK connection failed")

    adapter = ref_mod.RefinitivAdapter()
    with (
        patch.object(ref_mod, "_REFINITIV_SDK_AVAILABLE", True),
        patch.object(ref_mod, "rd", mock_rd),
        patch.object(ref_mod.settings, "refinitiv_app_key", "test-app-key"),
        patch("app.services.news.refinitiv._cache_get", return_value=None),
        patch("app.services.news.refinitiv._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_news("AAPL")

    assert result == []
