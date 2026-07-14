"""
NewsAPI.org adapter — general news aggregation.

Free tier: 100 requests/day, developer access only.
Paid tier: no rate limit for production.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

NEWSAPI_BASE = "https://newsapi.org/v2"


async def fetch_financial_news(
    query: str = "stocks OR earnings OR Fed OR inflation",
    from_hours: int = 24,
    page_size: int = 50,
) -> list[dict]:
    """
    Fetch recent financial news articles from NewsAPI.
    Returns normalized article dicts.
    """
    if not settings.newsapi_key:
        logger.warning("newsapi.key_missing")
        return []

    from_dt = (datetime.now(UTC) - timedelta(hours=from_hours)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{NEWSAPI_BASE}/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "from": from_dt,
                    "pageSize": page_size,
                    "apiKey": settings.newsapi_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for a in data.get("articles", []):
            articles.append(
                {
                    "source": "newsapi",
                    "source_id": a.get("url", ""),
                    "headline": a.get("title", ""),
                    "body": a.get("content") or a.get("description") or "",
                    "url": a.get("url", ""),
                    "published_at": a.get("publishedAt", datetime.now(UTC).isoformat()),
                    "tickers_mentioned": [],  # filled by NER pipeline
                    "sentiment": None,
                }
            )
        return articles

    except Exception:
        logger.exception("newsapi.fetch.error")
        return []


async def fetch_ticker_news(
    symbols: list[str],
    from_hours: int = 24,
    page_size: int = 30,
) -> list[dict]:
    """Fetch news articles specifically mentioning given ticker symbols."""
    query = " OR ".join(f'"{s}"' for s in symbols[:5])  # NewsAPI limits OR chains
    return await fetch_financial_news(query, from_hours, page_size)
