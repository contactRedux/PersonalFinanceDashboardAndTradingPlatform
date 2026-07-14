"""
Benzinga API adapter — structured financial news with ticker tagging.

Benzinga provides pre-tagged ticker mentions, making it ideal as a
primary financial news source. Requires a paid API key.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

BENZINGA_BASE = "https://api.benzinga.com/api/v2"


async def fetch_benzinga_news(
    symbols: list[str] | None = None,
    from_hours: int = 24,
    page_size: int = 50,
) -> list[dict]:
    """
    Fetch financial news from Benzinga.
    Returns pre-normalized article dicts with tickers_mentioned pre-filled
    from Benzinga's own ticker tagging.
    """
    if not settings.benzinga_api_key:
        logger.warning("benzinga.key_missing")
        return []

    params: dict = {
        "token": settings.benzinga_api_key,
        "displayOutput": "full",
        "pageSize": page_size,
    }
    if symbols:
        params["tickers"] = ",".join(symbols)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BENZINGA_BASE}/news", params=params)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        news_items = data if isinstance(data, list) else data.get("data", [])
        for item in news_items:
            # Extract Benzinga's pre-tagged tickers
            stocks = item.get("stocks", [])
            tickers = [s.get("name", "") for s in stocks if s.get("name")]

            articles.append({
                "source": "benzinga",
                "source_id": str(item.get("id", "")),
                "headline": item.get("title", ""),
                "body": item.get("body", "") or item.get("teaser", ""),
                "url": item.get("url", ""),
                "published_at": item.get("created", datetime.now(UTC).isoformat()),
                "tickers_mentioned": tickers,
                "sentiment": None,
            })
        return articles

    except Exception:
        logger.exception("benzinga.fetch.error")
        return []
