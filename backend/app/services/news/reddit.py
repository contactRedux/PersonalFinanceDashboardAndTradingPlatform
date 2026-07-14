"""
Reddit news adapter — fetches posts for a ticker from r/stocks, r/wallstreetbets, r/investing.

Uses praw with asyncio.to_thread.
Falls back to empty list when REDDIT_CLIENT_ID is absent.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_SUBREDDITS = ["stocks", "wallstreetbets", "investing"]
_RATE_LIMIT_PER_MIN = 60  # token-bucket capacity


class _TokenBucket:
    """Simple token-bucket rate limiter."""

    def __init__(self, rate: int) -> None:
        self._rate = rate  # tokens per second (1 per second = 60 per minute)
        self._tokens = float(rate)
        self._last = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self._rate, self._tokens + elapsed * (self._rate / 60.0))
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False


_bucket = _TokenBucket(_RATE_LIMIT_PER_MIN)


class RedditAdapter:
    """Fetches Reddit posts for a ticker from r/stocks, r/wallstreetbets, r/investing."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def get_news(self, ticker: str, limit: int = 10) -> list[dict]:
        """Return a list of Reddit post dicts for the given ticker.

        Each item: { title, url, source, subreddit, score, created_at, sentiment }
        Returns [] on missing credentials or any error.
        """
        if not self._settings.reddit_client_id:
            logger.debug("reddit.credentials_missing")
            return []

        if not _bucket.consume():
            logger.warning("reddit.rate_limited")
            return []

        try:
            return await asyncio.to_thread(self._fetch_sync, ticker, limit)
        except Exception:
            logger.exception("reddit.fetch.error", ticker=ticker)
            return []

    def _fetch_sync(self, ticker: str, limit: int) -> list[dict]:
        import praw  # noqa: PLC0415

        reddit = praw.Reddit(
            client_id=self._settings.reddit_client_id,
            client_secret=self._settings.reddit_client_secret,
            user_agent=self._settings.reddit_user_agent or "QuantNexus/1.0",
        )

        results: list[dict] = []
        per_sub = max(1, limit // len(_SUBREDDITS))

        for sub_name in _SUBREDDITS:
            try:
                subreddit = reddit.subreddit(sub_name)
                for submission in subreddit.search(ticker, limit=per_sub, sort="new"):
                    results.append(
                        {
                            "title": submission.title,
                            "url": f"https://reddit.com{submission.permalink}",
                            "source": "reddit",
                            "subreddit": sub_name,
                            "score": submission.score,
                            "created_at": datetime.fromtimestamp(
                                submission.created_utc, tz=UTC
                            ).isoformat(),
                            "sentiment": None,
                        }
                    )
            except Exception:
                logger.exception("reddit.subreddit.error", subreddit=sub_name)

        return results[:limit]
