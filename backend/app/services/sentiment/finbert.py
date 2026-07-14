"""
FinBERT inference wrapper.

Model: ProsusAI/finbert (from HuggingFace)
  - Financial domain BERT fine-tuned for sentiment classification
  - Labels: positive, negative, neutral
  - Runs on CPU for most deployments; GPU if CUDA available

The model is loaded lazily on first call and cached for the worker lifetime.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_pipeline = None


def _get_pipeline():
    """Lazily load FinBERT on first call."""
    global _pipeline
    if _pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
            logger.info("finbert.loading")
            _pipeline = hf_pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                max_length=512,
                truncation=True,
            )
            logger.info("finbert.loaded")
        except Exception:
            logger.exception("finbert.load_error")
            _pipeline = None
    return _pipeline


def score_text(text: str) -> dict:
    """
    Score a text using FinBERT.
    Returns: {"label": "bullish|bearish|neutral", "confidence": 0.0-1.0, "raw_score": float}
    """
    pipe = _get_pipeline()
    if pipe is None:
        return {"label": "neutral", "confidence": 0.5, "raw_score": 0.0, "model": "fallback"}

    try:
        result = pipe(text[:512])[0]  # type: ignore[index]
        label_map = {"positive": "bullish", "negative": "bearish", "neutral": "neutral"}
        raw_label = result["label"].lower()
        label = label_map.get(raw_label, "neutral")
        confidence = float(result["score"])
        # Convert to -1 to +1 score
        if label == "bullish":
            raw_score = confidence
        elif label == "bearish":
            raw_score = -confidence
        else:
            raw_score = 0.0
        return {
            "label": label, "confidence": confidence,
            "raw_score": raw_score, "model": "finbert",
        }
    except Exception:
        logger.exception("finbert.score_error")
        return {"label": "neutral", "confidence": 0.5, "raw_score": 0.0, "model": "fallback"}
