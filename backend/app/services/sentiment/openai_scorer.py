"""
OpenAI GPT-4o sentiment scorer.

Used only for high-impact articles (earnings calls, Fed statements, M&A).
This gates GPT-4o usage to prevent runaway costs.
"""

from __future__ import annotations

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Impact categories that warrant GPT-4o deep scoring
HIGH_IMPACT_CATEGORIES = frozenset({"earnings", "fed", "macro", "regulatory", "ma"})

_SYSTEM_PROMPT = """You are a financial sentiment analysis expert.
Analyze the provided news article and return a JSON response with:
- sentiment: "bullish" | "bearish" | "neutral"
- confidence: float 0.0 to 1.0
- raw_score: float -1.0 to 1.0 (negative=bearish, positive=bullish)
- impact_category: "earnings" | "macro" | "regulatory" | "ma" | "analyst" | "general"
- reasoning: brief explanation (max 50 words)
Respond ONLY with valid JSON."""


async def score_text_gpt4o(text: str, headline: str = "") -> dict:
    """
    Score a news article using GPT-4o.
    Returns a structured sentiment result.
    """
    if not settings.openai_api_key:
        logger.warning("openai.key_missing")
        return _fallback()

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        content = f"HEADLINE: {headline}\n\nARTICLE: {text[:3000]}"
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
        )

        import json

        result = json.loads(response.choices[0].message.content or "{}")
        return {
            "label": result.get("sentiment", "neutral"),
            "confidence": float(result.get("confidence", 0.5)),
            "raw_score": float(result.get("raw_score", 0.0)),
            "impact_category": result.get("impact_category", "general"),
            "reasoning": result.get("reasoning", ""),
            "model": "gpt-4o",
        }
    except Exception:
        logger.exception("openai.score_error")
        return _fallback()


def _fallback() -> dict:
    return {"label": "neutral", "confidence": 0.5, "raw_score": 0.0, "model": "fallback"}


def should_use_gpt4o(impact_category: str, confidence: float) -> bool:
    """
    Gate GPT-4o usage to high-impact articles with low FinBERT confidence.
    This prevents runaway API costs.
    """
    return (
        impact_category in HIGH_IMPACT_CATEGORIES
        or confidence < 0.65  # FinBERT uncertain → ask GPT-4o
    )
