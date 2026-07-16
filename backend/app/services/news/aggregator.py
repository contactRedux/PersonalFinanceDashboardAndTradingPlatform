"""
News aggregator — pulls from all configured sources, deduplicates,
and queues articles for sentiment scoring.

Sources:
  benzinga      — structured financial news (paid, optional)
  newsapi       — general financial headlines (paid, optional)
  reddit        — r/stocks, r/wallstreetbets sentiment
  sec_edgar     — SEC 8-K / 10-Q filings (free)
  stocktwits    — social cashtag stream (free, no key required)
  earningscall  — earnings call transcripts (free tier + paid)
  twitter       — cashtag tweets via Twitter API v2 (requires bearer token)
  yahoo_finance — Yahoo Finance news via yfinance (free, no key required)
  refinitiv     — Reuters / Refinitiv headlines (requires paid license + SDK)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import structlog

from app.services.news.benzinga import fetch_benzinga_news
from app.services.news.earningscall import EarningsCallAdapter
from app.services.news.newsapi import fetch_financial_news
from app.services.news.openinsider import OpenInsiderAdapter
from app.services.news.reddit import RedditAdapter
from app.services.news.refinitiv import RefinitivAdapter
from app.services.news.sec_edgar import SECEdgarAdapter
from app.services.news.stocktwits import StockTwitsAdapter
from app.services.news.twitter import TwitterAdapter
from app.services.news.yahoo_news import YahooNewsAdapter

logger = structlog.get_logger(__name__)

_reddit = RedditAdapter()
_sec_edgar = SECEdgarAdapter()
_stocktwits = StockTwitsAdapter()
_earningscall = EarningsCallAdapter()
_openinsider = OpenInsiderAdapter()
_twitter = TwitterAdapter()
_yahoo_news = YahooNewsAdapter()
_refinitiv = RefinitivAdapter()


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
    import asyncio  # noqa: PLC0415

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
    stocktwits_task = asyncio.create_task(
        _stocktwits.get_news(ticker, limit=10) if ticker else _empty()
    )
    earningscall_task = asyncio.create_task(
        _earningscall.get_news(ticker, limit=4) if ticker else _empty()
    )
    twitter_task = asyncio.create_task(
        _twitter.get_news(ticker, limit=10) if ticker else _empty()
    )
    yahoo_news_task = asyncio.create_task(
        _yahoo_news.get_news(ticker, limit=20) if ticker else _empty()
    )
    refinitiv_task = asyncio.create_task(
        _refinitiv.get_news(ticker, limit=10) if ticker else _empty()
    )

    (
        benzinga_articles,
        newsapi_articles,
        reddit_articles,
        sec_articles,
        stocktwits_articles,
        earningscall_articles,
        twitter_articles,
        yahoo_news_articles,
        refinitiv_articles,
    ) = await asyncio.gather(
        benzinga_task,
        newsapi_task,
        reddit_task,
        sec_task,
        stocktwits_task,
        earningscall_task,
        twitter_task,
        yahoo_news_task,
        refinitiv_task,
    )

    # Normalise reddit/sec/stocktwits/earningscall items to same shape
    for item in reddit_articles:
        item.setdefault("headline", item.get("title", ""))
        item.setdefault("published_at", item.get("created_at", datetime.now(UTC).isoformat()))

    for item in sec_articles:
        item.setdefault("headline", item.get("title", ""))
        item.setdefault("published_at", item.get("filed_at") or item.get("created_at", datetime.now(UTC).isoformat()))

    for item in stocktwits_articles:
        item.setdefault("published_at", item.get("created_at", datetime.now(UTC).isoformat()))

    for item in earningscall_articles:
        item.setdefault("published_at", item.get("date") or datetime.now(UTC).isoformat())

    for item in twitter_articles:
        item.setdefault("published_at", item.get("created_at", datetime.now(UTC).isoformat()))

    all_articles = (
        benzinga_articles
        + newsapi_articles
        + reddit_articles
        + sec_articles
        + stocktwits_articles
        + earningscall_articles
        + twitter_articles
        + yahoo_news_articles
        + refinitiv_articles
    )

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


async def get_insider_flow(symbol: str, days: int = 90) -> list[dict]:
    """
    Convenience function — fetch recent insider trades for a symbol.
    Used by the /fundamentals/{symbol}/insider-flow endpoint.
    """
    return await _openinsider.get_recent_trades(symbol, days=days)


async def get_stocktwits_stream(symbol: str) -> dict:
    """
    Convenience function — fetch StockTwits stream + bullish_pct.
    Used by the /ml/ai-score endpoint.
    """
    return await _stocktwits.get_stream(symbol)
