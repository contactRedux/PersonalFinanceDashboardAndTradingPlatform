"""
Unit tests for the Yahoo Finance news adapter.
All tests use mocked yfinance responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Sample yfinance news data (new format with "content" nested dict) ────────

SAMPLE_YF_NEWS_NEW_FORMAT = [
    {
        "uuid": "abc123",
        "providerPublishTime": 1730448000,  # 2024-11-01T08:00:00 UTC
        "type": "STORY",
        "content": {
            "title": "Apple beats Q4 earnings estimates with record revenue",
            "canonicalUrl": {"url": "https://finance.yahoo.com/news/apple-beats-q4"},
            "provider": {"displayName": "Bloomberg"},
        },
    },
    {
        "uuid": "def456",
        "providerPublishTime": 1730444400,  # 2024-11-01T07:00:00 UTC
        "type": "STORY",
        "content": {
            "title": "iPhone 16 demand surge lifts AAPL stock",
            "clickThroughUrl": {"url": "https://finance.yahoo.com/news/iphone-demand"},
            "provider": {"displayName": "Reuters"},
        },
    },
]

SAMPLE_YF_NEWS_OLD_FORMAT = [
    {
        "uuid": "old123",
        "title": "Apple Q4 revenue hits all-time high",
        "link": "https://finance.yahoo.com/news/apple-q4",
        "publisher": "CNBC",
        "providerPublishTime": 1730448000,
    },
]


# ─── YahooNewsAdapter ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_yahoo_news_returns_articles_new_format():
    """Test parsing of the nested 'content' dict format used by recent yfinance versions."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    mock_ticker = MagicMock()
    mock_ticker.news = SAMPLE_YF_NEWS_NEW_FORMAT

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=None),
        patch("app.services.news.yahoo_news._cache_set", new_callable=AsyncMock),
        patch("app.services.news.yahoo_news.asyncio.to_thread", new=AsyncMock(
            return_value=SAMPLE_YF_NEWS_NEW_FORMAT
        )),
    ):
        result = await adapter.get_articles("AAPL")

    assert len(result) == 2
    assert result[0]["headline"] == "Apple beats Q4 earnings estimates with record revenue"
    assert result[0]["source"] == "yahoo_finance"
    assert result[0]["url"] == "https://finance.yahoo.com/news/apple-beats-q4"
    assert result[0]["publisher"] == "Bloomberg"
    assert result[0]["source_id"] == "abc123"
    assert "AAPL" in result[0]["tickers_mentioned"]

    # second item uses clickThroughUrl
    assert result[1]["url"] == "https://finance.yahoo.com/news/iphone-demand"


@pytest.mark.anyio
async def test_yahoo_news_returns_articles_old_format():
    """Test parsing of the legacy flat format (title/link/publisher at top level)."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=None),
        patch("app.services.news.yahoo_news._cache_set", new_callable=AsyncMock),
        patch("app.services.news.yahoo_news.asyncio.to_thread", new=AsyncMock(
            return_value=SAMPLE_YF_NEWS_OLD_FORMAT
        )),
    ):
        result = await adapter.get_articles("AAPL")

    assert len(result) == 1
    assert result[0]["headline"] == "Apple Q4 revenue hits all-time high"
    assert result[0]["url"] == "https://finance.yahoo.com/news/apple-q4"
    assert result[0]["publisher"] == "CNBC"
    assert result[0]["source"] == "yahoo_finance"


@pytest.mark.anyio
async def test_yahoo_news_uses_cache():
    """When Redis has a cached result, no yfinance call is made."""
    import json  # noqa: PLC0415
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    cached = json.dumps([{
        "headline": "Cached AAPL headline",
        "source": "yahoo_finance",
        "source_id": "cached-uuid",
        "url": "https://finance.yahoo.com/cached",
        "published_at": "2024-11-01T10:00:00+00:00",
        "publisher": "Yahoo Finance",
        "tickers_mentioned": ["AAPL"],
    }])

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=cached),
        patch("app.services.news.yahoo_news.asyncio.to_thread") as mock_thread,
    ):
        result = await adapter.get_articles("AAPL")

    mock_thread.assert_not_called()
    assert len(result) == 1
    assert result[0]["headline"] == "Cached AAPL headline"


@pytest.mark.anyio
async def test_yahoo_news_returns_empty_on_yfinance_error():
    """If yfinance raises an exception, return [] gracefully."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=None),
        patch("app.services.news.yahoo_news._cache_set", new_callable=AsyncMock),
        patch("app.services.news.yahoo_news.asyncio.to_thread",
              new=AsyncMock(side_effect=Exception("yfinance network error"))),
    ):
        result = await adapter.get_articles("AAPL")

    assert result == []


@pytest.mark.anyio
async def test_yahoo_news_handles_empty_news_list():
    """Tickers with no news return an empty list."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=None),
        patch("app.services.news.yahoo_news._cache_set", new_callable=AsyncMock),
        patch("app.services.news.yahoo_news.asyncio.to_thread", new=AsyncMock(return_value=[])),
    ):
        result = await adapter.get_articles("OBSCURETICKER")

    assert result == []


@pytest.mark.anyio
async def test_yahoo_news_get_news_respects_limit():
    """get_news() truncates results to the specified limit."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    # Build 5 articles
    articles = [
        {
            "headline": f"Headline {i}",
            "source": "yahoo_finance",
            "source_id": str(i),
            "url": f"https://finance.yahoo.com/{i}",
            "published_at": "2024-11-01T10:00:00+00:00",
            "publisher": "Yahoo Finance",
            "tickers_mentioned": ["AAPL"],
        }
        for i in range(5)
    ]

    adapter = YahooNewsAdapter()
    with patch.object(adapter, "get_articles", new=AsyncMock(return_value=articles)):
        result = await adapter.get_news("AAPL", limit=3)

    assert len(result) == 3


@pytest.mark.anyio
async def test_yahoo_news_published_at_from_unix_timestamp():
    """providerPublishTime (Unix int) is correctly converted to ISO format."""
    from app.services.news.yahoo_news import YahooNewsAdapter  # noqa: PLC0415

    news_item = [{
        "uuid": "ts-test",
        "providerPublishTime": 1730448000,  # 2024-11-01T08:00:00 UTC
        "content": {
            "title": "Test timestamp conversion",
            "canonicalUrl": {"url": "https://example.com"},
            "provider": {"displayName": "Test"},
        },
    }]

    adapter = YahooNewsAdapter()
    with (
        patch("app.services.news.yahoo_news._cache_get", return_value=None),
        patch("app.services.news.yahoo_news._cache_set", new_callable=AsyncMock),
        patch("app.services.news.yahoo_news.asyncio.to_thread", new=AsyncMock(return_value=news_item)),
    ):
        result = await adapter.get_articles("AAPL")

    assert len(result) == 1
    # Should parse the unix timestamp and produce an ISO string
    pub = result[0]["published_at"]
    assert "2024-11-01" in pub
