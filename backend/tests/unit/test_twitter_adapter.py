"""
Unit tests for the Twitter/X adapter.
All tests use mocked Tweepy responses — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Twitter Adapter ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_twitter_returns_empty_when_no_bearer_token():
    """Without TWITTER_BEARER_TOKEN, get_cashtag_tweets() returns []."""
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    adapter = TwitterAdapter()
    with patch.object(twitter_mod.settings, "twitter_bearer_token", ""):
        result = await adapter.get_cashtag_tweets("AAPL")

    assert result == []


@pytest.mark.anyio
async def test_twitter_returns_tweets_when_configured():
    """When a bearer token is set and Tweepy returns data, get_cashtag_tweets() maps tweets."""
    import tweepy  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    # Build mock tweet objects
    mock_tweet_1 = MagicMock(spec=tweepy.Tweet)
    mock_tweet_1.id = 1234567890
    mock_tweet_1.text = "$AAPL looks bullish today! Great earnings ahead."
    mock_tweet_1.author_id = 9001
    mock_tweet_1.created_at = datetime(2024, 11, 1, 10, 0, 0, tzinfo=UTC)
    mock_tweet_1.public_metrics = {"retweet_count": 5, "like_count": 20}

    mock_tweet_2 = MagicMock(spec=tweepy.Tweet)
    mock_tweet_2.id = 1234567891
    mock_tweet_2.text = "Selling $AAPL here, too extended."
    mock_tweet_2.author_id = 9002
    mock_tweet_2.created_at = datetime(2024, 11, 1, 9, 30, 0, tzinfo=UTC)
    mock_tweet_2.public_metrics = {"retweet_count": 2, "like_count": 8}

    mock_user_1 = MagicMock()
    mock_user_1.id = 9001
    mock_user_1.username = "bullish_trader"

    mock_user_2 = MagicMock()
    mock_user_2.id = 9002
    mock_user_2.username = "bearish_analyst"

    mock_response = MagicMock()
    mock_response.data = [mock_tweet_1, mock_tweet_2]
    mock_response.includes = {"users": [mock_user_1, mock_user_2]}

    mock_tweepy_client = MagicMock()
    mock_tweepy_client.search_recent_tweets.return_value = mock_response

    adapter = TwitterAdapter()
    with (
        patch.object(twitter_mod.settings, "twitter_bearer_token", "test-bearer-token"),
        patch("app.services.news.twitter.tweepy.Client", return_value=mock_tweepy_client),
        patch("app.services.news.twitter._cache_get", return_value=None),
        patch("app.services.news.twitter._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_cashtag_tweets("AAPL", max_results=10)

    assert len(result) == 2
    assert result[0]["tweet_id"] == "1234567890"
    assert "$AAPL" in result[0]["message"]
    assert result[0]["username"] == "bullish_trader"
    assert result[0]["source"] == "twitter"
    assert result[1]["username"] == "bearish_analyst"


@pytest.mark.anyio
async def test_twitter_uses_cache():
    """When Redis has a cached result, no Tweepy API call is made."""
    import json  # noqa: PLC0415
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    cached = json.dumps([{
        "tweet_id": "9999",
        "message": "$AAPL cached tweet",
        "created_at": "2024-11-01T10:00:00+00:00",
        "username": "cached_user",
        "metrics": {},
        "source": "twitter",
    }])

    adapter = TwitterAdapter()
    with (
        patch.object(twitter_mod.settings, "twitter_bearer_token", "test-bearer-token"),
        patch("app.services.news.twitter._cache_get", return_value=cached),
        patch("app.services.news.twitter.tweepy.Client") as mock_tweepy_cls,
    ):
        result = await adapter.get_cashtag_tweets("AAPL")

    mock_tweepy_cls.assert_not_called()
    assert len(result) == 1
    assert result[0]["tweet_id"] == "9999"


@pytest.mark.anyio
async def test_twitter_returns_empty_when_no_results():
    """When Tweepy returns None data, return []."""
    import tweepy  # noqa: PLC0415
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    mock_response = MagicMock()
    mock_response.data = None

    mock_tweepy_client = MagicMock()
    mock_tweepy_client.search_recent_tweets.return_value = mock_response

    adapter = TwitterAdapter()
    with (
        patch.object(twitter_mod.settings, "twitter_bearer_token", "test-bearer-token"),
        patch("app.services.news.twitter.tweepy.Client", return_value=mock_tweepy_client),
        patch("app.services.news.twitter._cache_get", return_value=None),
        patch("app.services.news.twitter._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_cashtag_tweets("AAPL")

    assert result == []


@pytest.mark.anyio
async def test_twitter_caps_max_results_at_10():
    """Free tier max is 10; requesting more should be capped at 10."""
    import tweepy  # noqa: PLC0415
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    mock_response = MagicMock()
    mock_response.data = None
    mock_response.includes = {}

    mock_tweepy_client = MagicMock()
    mock_tweepy_client.search_recent_tweets.return_value = mock_response

    adapter = TwitterAdapter()
    with (
        patch.object(twitter_mod.settings, "twitter_bearer_token", "test-bearer-token"),
        patch("app.services.news.twitter.tweepy.Client", return_value=mock_tweepy_client),
        patch("app.services.news.twitter._cache_get", return_value=None),
        patch("app.services.news.twitter._cache_set", new_callable=AsyncMock),
    ):
        await adapter.get_cashtag_tweets("AAPL", max_results=50)

    call_kwargs = mock_tweepy_client.search_recent_tweets.call_args.kwargs
    assert call_kwargs["max_results"] == 10


@pytest.mark.anyio
async def test_twitter_get_news_returns_aggregator_format():
    """get_news() returns dicts with 'headline', 'source', 'published_at' etc."""
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415

    mock_tweets = [
        {
            "tweet_id": "1111",
            "message": "$AAPL to the moon!",
            "created_at": "2024-11-01T10:00:00+00:00",
            "username": "moon_trader",
            "metrics": {},
            "source": "twitter",
        }
    ]

    adapter = TwitterAdapter()
    with patch.object(adapter, "get_cashtag_tweets", new=AsyncMock(return_value=mock_tweets)):
        result = await adapter.get_news("AAPL", limit=10)

    assert len(result) == 1
    assert result[0]["headline"] == "$AAPL to the moon!"
    assert result[0]["source"] == "twitter"
    assert result[0]["url"].startswith("https://x.com/i/web/status/")
    assert result[0]["published_at"] == "2024-11-01T10:00:00+00:00"


@pytest.mark.anyio
async def test_twitter_returns_empty_on_tweepy_exception():
    """TweepyException is caught gracefully and returns []."""
    import tweepy  # noqa: PLC0415
    from app.services.news.twitter import TwitterAdapter  # noqa: PLC0415
    import app.services.news.twitter as twitter_mod  # noqa: PLC0415

    mock_tweepy_client = MagicMock()
    mock_tweepy_client.search_recent_tweets.side_effect = tweepy.TweepyException("Rate limit")

    adapter = TwitterAdapter()
    with (
        patch.object(twitter_mod.settings, "twitter_bearer_token", "test-bearer-token"),
        patch("app.services.news.twitter.tweepy.Client", return_value=mock_tweepy_client),
        patch("app.services.news.twitter._cache_get", return_value=None),
        patch("app.services.news.twitter._cache_set", new_callable=AsyncMock),
    ):
        result = await adapter.get_cashtag_tweets("AAPL")

    assert result == []
