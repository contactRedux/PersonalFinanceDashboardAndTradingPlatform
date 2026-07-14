"""Sentiment scoring Celery tasks — full implementation in ST-8."""
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.score_article")
def score_article(article_id: str) -> dict:
    """Run FinBERT + optionally GPT-4o scoring on a news article."""
    # Implemented in ST-8
    return {"article_id": article_id, "status": "pending_st8"}


@celery_app.task(name="tasks.update_ticker_sentiment_aggregate")
def update_ticker_sentiment_aggregate(symbol: str) -> dict:
    """Recompute the time-decay weighted aggregate sentiment score for a symbol."""
    # Implemented in ST-8
    return {"symbol": symbol, "status": "pending_st8"}
