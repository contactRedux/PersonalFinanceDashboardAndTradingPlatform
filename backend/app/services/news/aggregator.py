"""
News aggregator — pulls from all configured sources, deduplicates,
and queues articles for sentiment scoring.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import structlog

from app.services.news.benzinga import fetch_benzinga_news
from app.services.news.newsapi import fetch_financial_news
from app.services.news.reddit import RedditAdapter
from app.services.news.sec_edgar import SECEdgarAdapter

logger = structlog.get_logger(__name__)

_reddit = RedditAdapter()
_sec_edgar = SECEdgarAdapter()


def _article_fingerprint(headline: str, source: str) -> str:
    """Create a deduplication key from headline + source."""
    text = f"{source}:{headline.lower().strip()}"
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()  # noqa: S324


async def fetch_and_aggregate(
    symbols: list[str] | None = None,
    from_hours: int = 6,
    max_articles: int = 100,
) -> list[dict]:
    """
    Fetch from all configured sources, deduplicate, and return a merged list
    sorted by publication time (newest first).
    """
    import asyncio

    ticker = symbols[0] if symbols else ""

    async def _empty() -> list[dict]:
        return []

    benzinga_task = asyncio.create_task(fetch_benzinga_news(symbols=symbols, from_hours=from_hours))
    newsapi_task = asyncio.create_task(fetch_financial_news(from_hours=from_hours))
    reddit_task = asyncio.create_task(
        _reddit.get_news(ticker, limit=10) if ticker else _empty()
    )
    sec_task = asyncio.create_task(
        _sec_edgar.get_news(ticker, limit=5) if ticker else _empty()
    )

    benzinga_articles, newsapi_articles, reddit_articles, sec_articles = await asyncio.gather(
        benzinga_task, newsapi_task, reddit_task, sec_task
    )

    # Normalise reddit/sec items to same shape as benzinga/newsapi
    for item in reddit_articles:
        item.setdefault("headline", item.get("title", ""))
        item.setdefault("published_at", item.get("created_at", datetime.now(UTC).isoformat()))

    for item in sec_articles:
        item.setdefault("headline", item.get("title", ""))
        item.setdefault("published_at", item.get("filed_at") or item.get("created_at", datetime.now(UTC).isoformat()))

    all_articles = benzinga_articles + newsapi_articles + reddit_articles + sec_articles

    # Deduplicate by fingerprint
    seen: set[str] = set()
    unique: list[dict] = []
    for article in all_articles:
        fp = _article_fingerprint(article["headline"], article["source"])
        if fp not in seen:
            seen.add(fp)
            article["_fingerprint"] = fp
            unique.append(article)

    # Sort by publication time (newest first)
    def _parse_time(a: dict) -> datetime:
        try:
            return datetime.fromisoformat(a.get("published_at", "").replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(UTC)

    unique.sort(key=_parse_time, reverse=True)
    return unique[:max_articles]
