"""
Sentiment aggregator — computes per-ticker time-decay weighted aggregate scores.

Algorithm:
  - Fetch all scored articles mentioning a ticker from the last 24 hours
  - Apply exponential time decay: weight = exp(-lambda * hours_ago)
  - Compute weighted average of raw_scores
  - Determine dominant label from weighted vote
  - Cache result in Redis (5 min TTL) + persist to MongoDB
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import structlog

logger = structlog.get_logger(__name__)

DECAY_LAMBDA = 0.15  # Controls recency bias: higher → faster decay


def _time_decay_weight(published_at: str) -> float:
    """Compute exponential decay weight based on article age."""
    try:
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        hours_ago = (datetime.now(UTC) - pub_dt).total_seconds() / 3600
        return math.exp(-DECAY_LAMBDA * max(hours_ago, 0))
    except (ValueError, TypeError):
        return 0.5  # neutral weight for unparseable dates


def compute_aggregate(articles: list[dict]) -> dict:
    """
    Compute the aggregate sentiment for a list of scored articles.
    Each article must have a `sentiment` dict with `raw_score` and `confidence`.
    """
    if not articles:
        return {
            "score": 0.0,
            "dominant_label": "neutral",
            "article_count": 0,
            "confidence": 0.0,
        }

    total_weight = 0.0
    weighted_score = 0.0
    weighted_confidence = 0.0

    for article in articles:
        sentiment = article.get("sentiment") or {}
        raw_score = float(sentiment.get("raw_score", 0.0))
        confidence = float(sentiment.get("confidence", 0.5))
        weight = _time_decay_weight(article.get("published_at", ""))

        total_weight += weight
        weighted_score += raw_score * weight * confidence
        weighted_confidence += confidence * weight

    if total_weight == 0:
        return {
            "score": 0.0,
            "dominant_label": "neutral",
            "article_count": len(articles),
            "confidence": 0.0,
        }

    final_score = weighted_score / total_weight
    avg_confidence = weighted_confidence / total_weight

    if final_score > 0.15:
        dominant_label = "bullish"
    elif final_score < -0.15:
        dominant_label = "bearish"
    else:
        dominant_label = "neutral"

    return {
        "score": round(final_score, 4),
        "dominant_label": dominant_label,
        "article_count": len(articles),
        "confidence": round(avg_confidence, 4),
    }
