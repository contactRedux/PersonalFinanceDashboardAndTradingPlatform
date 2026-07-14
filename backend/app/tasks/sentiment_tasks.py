"""
Celery tasks for sentiment scoring.

All NLP operations run asynchronously in Celery workers so they
never block the FastAPI request path.

Task flow:
  1. score_article(article_id) — FinBERT + optionally GPT-4o
  2. update_ticker_sentiment_aggregate(symbol) — recompute aggregate
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="tasks.score_article",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def score_article(self, article: dict) -> dict:  # type: ignore[override]
    """
    Score a news article using FinBERT (+ optionally GPT-4o for high-impact).
    Persists the scored article to MongoDB and updates Redis cache.

    `article` must have: source, headline, body, published_at, tickers_mentioned.
    """
    from app.services.sentiment.finbert import score_text
    from app.services.sentiment.ner_extractor import extract_tickers
    from app.services.sentiment.openai_scorer import score_text_gpt4o, should_use_gpt4o

    try:
        headline = article.get("headline", "")
        body = article.get("body", "")
        text_to_score = f"{headline}. {body}"[:1024]

        # Step 1: FinBERT scoring
        finbert_result = score_text(text_to_score)

        # Step 2: NER ticker extraction if not already tagged
        if not article.get("tickers_mentioned"):
            article["tickers_mentioned"] = extract_tickers(text_to_score)

        # Step 3: Determine impact category (simple heuristic)
        impact_category = _classify_impact(headline)

        # Step 4: Optionally invoke GPT-4o
        gpt4o_result = None
        if should_use_gpt4o(impact_category, finbert_result.get("confidence", 0.5)):
            import asyncio

            try:
                loop = asyncio.new_event_loop()
                gpt4o_result = loop.run_until_complete(score_text_gpt4o(text_to_score, headline))
                loop.close()
            except Exception:
                logger.warning("tasks.score_article.gpt4o_failed")

        # Step 5: Composite score
        if gpt4o_result:
            composite_score = (
                finbert_result.get("raw_score", 0.0) * 0.4
                + gpt4o_result.get("raw_score", 0.0) * 0.6
            )
            dominant_label = gpt4o_result.get("label", finbert_result.get("label", "neutral"))
        else:
            composite_score = finbert_result.get("raw_score", 0.0)
            dominant_label = finbert_result.get("label", "neutral")

        scored_article = {
            **article,
            "sentiment": {
                "finbert_score": finbert_result.get("raw_score", 0.0),
                "finbert_confidence": finbert_result.get("confidence", 0.5),
                "openai_score": gpt4o_result.get("raw_score") if gpt4o_result else None,
                "openai_confidence": gpt4o_result.get("confidence") if gpt4o_result else None,
                "composite_score": composite_score,
                "label": dominant_label,
                "impact_category": impact_category,
            },
            "processed_at": datetime.now(UTC).isoformat(),
        }

        # Step 6: Persist to MongoDB
        _save_to_mongodb(scored_article)

        # Step 7: Update aggregate for each mentioned ticker
        for symbol in article.get("tickers_mentioned", []):
            update_ticker_sentiment_aggregate.delay(symbol)

        return {"status": "scored", "label": dominant_label, "score": composite_score}

    except Exception as exc:
        logger.exception("tasks.score_article.error")
        raise self.retry(exc=exc) from exc


@celery_app.task(name="tasks.update_ticker_sentiment_aggregate")
def update_ticker_sentiment_aggregate(symbol: str) -> dict:
    """
    Recompute the time-decay weighted aggregate sentiment score for a symbol.
    Updates Redis cache with the result.
    """
    from app.services.sentiment.aggregator import compute_aggregate

    articles = _fetch_recent_articles_for_symbol(symbol, hours=24)
    aggregate = compute_aggregate(articles)

    # Update Redis cache
    _update_redis_sentiment(symbol, aggregate)

    return {"symbol": symbol, "aggregate": aggregate}


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _classify_impact(headline: str) -> str:
    """Simple keyword-based impact classification."""
    headline_lower = headline.lower()
    if any(k in headline_lower for k in ["earnings", "revenue", "profit", "eps", "guidance"]):
        return "earnings"
    if any(k in headline_lower for k in ["fed", "fomc", "rate", "inflation", "gdp", "cpi"]):
        return "macro"
    if any(k in headline_lower for k in ["merger", "acquisition", "deal", "buyout", "m&a"]):
        return "ma"
    if any(k in headline_lower for k in ["sec", "lawsuit", "fine", "regulatory", "ban"]):
        return "regulatory"
    if any(k in headline_lower for k in ["analyst", "upgrade", "downgrade", "target", "rating"]):
        return "analyst"
    return "general"


def _save_to_mongodb(article: dict) -> None:
    """Save a scored article to MongoDB synchronously (Celery worker context)."""
    try:
        import pymongo

        from app.config import get_settings

        settings = get_settings()
        client = pymongo.MongoClient(settings.mongodb_url)
        db = client[settings.mongodb_database]
        # Upsert by fingerprint to avoid duplicates
        fp = article.get("_fingerprint", article.get("source_id", ""))
        db.news_articles.replace_one(
            {"_fingerprint": fp} if fp else {"source_id": article.get("source_id", "")},
            article,
            upsert=True,
        )
    except Exception:
        logger.exception("mongodb.save_error")


def _fetch_recent_articles_for_symbol(symbol: str, hours: int = 24) -> list[dict]:
    """Fetch scored articles mentioning a symbol from MongoDB."""
    try:
        import pymongo

        from app.config import get_settings

        settings = get_settings()
        client = pymongo.MongoClient(settings.mongodb_url)
        db = client[settings.mongodb_database]
        cursor = db.news_articles.find(
            {
                "tickers_mentioned": symbol,
                "sentiment": {"$ne": None},
            }
        ).limit(50)
        return list(cursor)
    except Exception:
        logger.exception("mongodb.fetch_error")
        return []


def _update_redis_sentiment(symbol: str, aggregate: dict) -> None:
    """Update Redis sentiment cache synchronously."""
    try:
        import redis

        from app.config import get_settings

        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        r.setex(
            f"sentiment:{symbol.upper()}",
            300,  # 5 min TTL
            json.dumps(
                {**aggregate, "symbol": symbol, "updated_at": datetime.now(UTC).isoformat()}
            ),
        )
    except Exception:
        logger.exception("redis.sentiment_update_error")
