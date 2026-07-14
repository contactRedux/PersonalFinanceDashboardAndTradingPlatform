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

logger = structlog.get_logger(__name__)


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
    # Fetch from both sources concurrently
    import asyncio

    benzinga_task = asyncio.create_task(fetch_benzinga_news(symbols=symbols, from_hours=from_hours))
    newsapi_task = asyncio.create_task(fetch_financial_news(from_hours=from_hours))
    benzinga_articles, newsapi_articles = await asyncio.gather(benzinga_task, newsapi_task)

    all_articles = benzinga_articles + newsapi_articles

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
