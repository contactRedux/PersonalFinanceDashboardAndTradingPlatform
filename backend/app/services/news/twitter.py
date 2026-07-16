"""
Twitter/X adapter — cashtag search via Twitter API v2 (free tier).

Searches for tweets mentioning a cashtag (e.g. $AAPL) using the v2 recent search
endpoint. Results are cached in Redis for 15 minutes to respect the strict free-tier
rate limit (1 request per 15 minutes per endpoint per app).

Free tier limits:
  - 1 app per project
  - 500,000 tweets per month (read)
  - Recent search: up to 10 results per request on free tier
  - Rate limit: 1 request per 15 minutes per endpoint

Configuration:
  TWITTER_BEARER_TOKEN — App-only bearer token from developer.twitter.com

Requires:
  tweepy>=4.14.0 (in pyproject.toml dependencies)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
import tweepy

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_CACHE_TTL = 60 * 15  # 15 minutes (match rate limit window)


# ─── Redis cache helpers ──────────────────────────────────────────────────────

async def _cache_get(key: str) -> str | None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        return await redis.get(key)
    except Exception:  # noqa: BLE001
        return None


async def _cache_set(key: str, value: str, ttl: int = _CACHE_TTL) -> None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        await redis.setex(key, ttl, value)
    except Exception:  # noqa: BLE001
        pass


# ─── Adapter ──────────────────────────────────────────────────────────────────

class TwitterAdapter:
    """
    Searches Twitter/X for cashtag mentions using the v2 recent search API.

    Rate limit: 1 request per 15 minutes per cashtag (enforced via Redis TTL cache).
    Results are cached in Redis for 900 seconds (15 minutes).

    Each returned item:
      message, created_at, username, tweet_id, source="twitter"
    """

    def _is_available(self) -> bool:
        return bool(settings.twitter_bearer_token)

    async def get_cashtag_tweets(
        self,
        symbol: str,
        max_results: int = 10,
    ) -> list[dict]:
        """
        Fetch recent tweets mentioning `$SYMBOL` cashtag (last 7 days).

        Parameters
        ----------
        symbol      : Ticker symbol, e.g. "AAPL" → searches "$AAPL"
        max_results : Number of tweets to return (1–10 on free tier, max 100 on paid)

        Returns a list of tweet dicts. Returns [] when no token is configured or
        on API error.
        """
        if not self._is_available():
            logger.debug("twitter.no_bearer_token")
            return []

        sym = symbol.upper()
        cache_key = f"twitter:cashtag:{sym}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            tweets = await self._fetch(sym, max_results)
            await _cache_set(cache_key, json.dumps(tweets))
            return tweets
        except Exception:  # noqa: BLE001
            logger.debug("twitter.fetch_error", symbol=sym)
            return []

    async def _fetch(self, symbol: str, max_results: int) -> list[dict]:
        import asyncio  # noqa: PLC0415

        client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            wait_on_rate_limit=False,
        )

        query = f"${symbol} -is:retweet lang:en"
        # Free tier caps max_results at 10; cap silently
        safe_max = max(1, min(max_results, 10))

        def _sync_search() -> list[dict]:
            try:
                response = client.search_recent_tweets(
                    query=query,
                    max_results=safe_max,
                    tweet_fields=["created_at", "text", "author_id", "public_metrics"],
                    expansions=["author_id"],
                    user_fields=["username"],
                )
            except tweepy.TweepyException as exc:
                logger.debug("twitter.api_error", error=str(exc), symbol=symbol)
                return []

            if response is None or response.data is None:
                return []

            # Build author_id → username mapping from includes
            users = {}
            if response.includes and "users" in response.includes:
                for user in response.includes["users"]:
                    users[user.id] = user.username

            now_iso = datetime.now(UTC).isoformat()
            tweets = []
            for tweet in response.data:
                created = (
                    tweet.created_at.isoformat()
                    if tweet.created_at
                    else now_iso
                )
                tweets.append({
                    "tweet_id": str(tweet.id),
                    "message": tweet.text,
                    "created_at": created,
                    "username": users.get(tweet.author_id, ""),
                    "metrics": tweet.public_metrics or {},
                    "source": "twitter",
                })
            return tweets

        return await asyncio.to_thread(_sync_search)

    async def get_news(self, symbol: str, limit: int = 10) -> list[dict]:
        """
        News-aggregator-compatible interface.
        Returns a list of article dicts with standard keys.
        """
        tweets = await self.get_cashtag_tweets(symbol, max_results=limit)
        articles = []
        for tweet in tweets:
            articles.append({
                "headline": tweet["message"][:280],
                "source": "twitter",
                "source_id": tweet.get("tweet_id", ""),
                "url": f"https://x.com/i/web/status/{tweet.get('tweet_id', '')}",
                "published_at": tweet["created_at"],
                "sentiment": None,
                "tickers_mentioned": [symbol],
            })
        return articles
