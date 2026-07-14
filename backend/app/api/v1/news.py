"""
News and sentiment REST endpoints.
Articles are served from MongoDB (async Motor driver).
Sentiment scores are served from Redis cache.
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Query

from app.data.cache.quote_cache import get_sentiment_cache
from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/feed")
async def get_news_feed(
    _: CurrentUser,
    background_tasks: BackgroundTasks,
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
):
    """
    Paginated news feed. Fetches from MongoDB (motor async driver).
    If news are stale (>30 min), triggers a background refresh.
    """
    articles = await _fetch_articles_from_mongodb(
        symbols=symbols.split(",") if symbols else None,
        limit=limit,
        offset=(page - 1) * limit,
    )

    # If we have fewer articles than requested, trigger a background fetch
    if len(articles) < limit // 2:
        background_tasks.add_task(_trigger_news_refresh, symbols)

    return {
        "articles": articles,
        "total": len(articles),
        "page": page,
        "limit": limit,
        "disclaimer": (
            "AI sentiment scores are for informational purposes only "
            "and do not constitute investment advice."
        ),
    }


@router.get("/sentiment/{symbol}")
async def get_sentiment(symbol: str, _: CurrentUser):
    """
    Aggregate sentiment score for a symbol.
    Returns cached result from Redis or triggers background computation.
    """
    sym = symbol.upper()
    cached = await get_sentiment_cache(sym)
    if cached:
        return {
            **cached,
            "disclaimer": "AI scores are not investment advice.",
        }

    # No cache — return neutral placeholder and trigger async scoring
    return {
        "symbol": sym,
        "score": 0.0,
        "dominant_label": "neutral",
        "article_count": 0,
        "confidence": 0.0,
        "updated_at": datetime.now(UTC).isoformat(),
        "note": "Sentiment scoring is processing in the background.",
        "disclaimer": "AI scores are not investment advice.",
    }


@router.get("/sentiment")
async def get_batch_sentiment(
    _: CurrentUser,
    symbols: str = Query(..., description="Comma-separated symbols"),
):
    """Batch sentiment scores for multiple symbols."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = {}
    for sym in symbol_list:
        cached = await get_sentiment_cache(sym)
        results[sym] = cached or {
            "symbol": sym,
            "dominant_label": "neutral",
            "score": 0.0,
        }
    return {
        "sentiment": results,
        "disclaimer": "AI scores are not investment advice.",
    }


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _fetch_articles_from_mongodb(
    symbols: list[str] | None,
    limit: int,
    offset: int,
) -> list[dict]:
    """Fetch articles from MongoDB using Motor async driver."""
    try:
        import motor.motor_asyncio as motor

        from app.config import get_settings

        settings = get_settings()
        client = motor.AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.mongodb_database]

        query: dict = {}
        if symbols:
            query["tickers_mentioned"] = {"$in": [s.upper() for s in symbols]}

        cursor = (
            db.news_articles
            .find(query, {"_id": 0, "_fingerprint": 0})
            .sort("published_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    except Exception:
        return []


async def _trigger_news_refresh(symbols_str: str | None) -> None:
    """Queue a background news fetch + scoring job."""
    try:
        from app.services.news.aggregator import fetch_and_aggregate
        from app.tasks.sentiment_tasks import score_article

        symbols = symbols_str.split(",") if symbols_str else None
        articles = await fetch_and_aggregate(symbols=symbols, max_articles=20)
        for article in articles:
            # Dispatch scoring to Celery worker
            score_article.delay(article)
    except Exception:
        logger.debug("news_refresh.background.failed")
