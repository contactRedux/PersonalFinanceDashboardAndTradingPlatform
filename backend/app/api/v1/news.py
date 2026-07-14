"""News and sentiment REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.data.cache.quote_cache import get_sentiment_cache
from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/feed")
async def get_news_feed(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    _: dict = CurrentUser,
):
    """Paginated news feed, optionally filtered by symbols. Implemented in ST-8."""
    return {"articles": [], "total": 0, "page": page, "limit": limit}


@router.get("/sentiment/{symbol}")
async def get_sentiment(symbol: str, _: dict = CurrentUser):
    """Aggregate sentiment score for a symbol. Returns cached result if available."""
    cached = await get_sentiment_cache(symbol)
    if cached:
        return cached
    return {
        "symbol": symbol.upper(),
        "score_1h": None,
        "score_4h": None,
        "score_1d": None,
        "dominant_label": "neutral",
        "article_count_1h": 0,
        "note": "Sentiment pipeline in ST-8",
    }


@router.get("/sentiment")
async def get_batch_sentiment(
    symbols: str = Query(..., description="Comma-separated symbols"),
    _: dict = CurrentUser,
):
    """Batch sentiment scores for multiple symbols."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = {}
    for sym in symbol_list:
        cached = await get_sentiment_cache(sym)
        results[sym] = cached or {"symbol": sym, "dominant_label": "neutral"}
    return {"sentiment": results}
