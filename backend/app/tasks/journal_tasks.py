"""
Celery task — AI trade journal analysis.

After an order is filled, analyze_trade is dispatched to:
  1. Fetch the order from PostgreSQL
  2. Read the symbol's Redis-cached sentiment score
  3. Compute a mocked technical context (RSI + MACD signal)
  4. Call OpenAI GPT-4o to generate a 2–3 sentence trade analysis
  5. Persist a journal entry to MongoDB trade_journal collection
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_DEMO_ANALYSIS = (
    "Demo mode: no OpenAI key configured. Trade placed at market conditions."
)


@celery_app.task(
    name="journal_tasks.analyze_trade",
    bind=False,
    max_retries=0,
)
def analyze_trade(order_id: str) -> dict:
    """
    Analyze a filled trade and persist an AI-generated journal entry to MongoDB.

    When dependencies (OpenAI, MongoDB) are unavailable, degrades gracefully.
    """
    try:
        return asyncio.run(_analyze(order_id))
    except Exception:  # noqa: BLE001
        logger.exception("journal_tasks.analyze_trade.error", order_id=order_id)
        return {"status": "error", "order_id": order_id}


async def _analyze(order_id: str) -> dict:
    """Async implementation — runs inside asyncio.run() from the sync Celery task."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.order import Order  # noqa: PLC0415

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order: Order | None = result.scalar_one_or_none()

    if order is None:
        logger.warning("journal_tasks.order_not_found", order_id=order_id)
        return {"status": "skipped", "reason": "order_not_found"}

    symbol: str = order.symbol
    user_id: str = str(order.user_id)
    side: str = order.side
    quantity: float = order.quantity
    entry_price: float | None = order.filled_avg_price

    # ── Step 1: Redis sentiment score ─────────────────────────────────────────
    sentiment_score: float | None = _read_sentiment(symbol)

    # ── Step 2: Technical context (mocked — no external API calls) ────────────
    technical_context: dict = _mock_technical_context(symbol)

    # ── Step 3: OpenAI analysis ───────────────────────────────────────────────
    ai_analysis: str = await _generate_analysis(
        symbol, side, quantity, entry_price, sentiment_score, technical_context
    )

    # ── Step 4: Persist to MongoDB ────────────────────────────────────────────
    doc = {
        "order_id": order_id,
        "user_id": user_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "entry_price": entry_price,
        "sentiment_score": sentiment_score,
        "technical_context": technical_context,
        "ai_analysis": ai_analysis,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await _save_journal_entry(doc)

    logger.info("journal_tasks.entry_saved", order_id=order_id, symbol=symbol)
    return {"status": "ok", "order_id": order_id}


# ─── Internal helpers ──────────────────────────────────────────────────────────


def _read_sentiment(symbol: str) -> float | None:
    """Read the symbol's aggregate sentiment score from Redis (key: sentiment:{symbol})."""
    try:
        import redis  # noqa: PLC0415

        from app.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        r = redis.from_url(settings.redis_url, decode_responses=True)
        raw = r.get(f"sentiment:{symbol.upper()}")
        if raw is None:
            return None
        data = json.loads(raw)
        return float(data.get("score", 0.0))
    except Exception:  # noqa: BLE001
        logger.warning("journal_tasks.redis_sentiment_unavailable", symbol=symbol)
        return None


def _mock_technical_context(symbol: str) -> dict:  # noqa: ARG001
    """Return a fixed demo technical context (no external API calls)."""
    return {
        "rsi": 54.2,
        "macd_signal": "bullish_crossover",
        "note": "demo_mode",
    }


async def _generate_analysis(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float | None,
    sentiment_score: float | None,
    technical_context: dict,
) -> str:
    """Call OpenAI GPT-4o for trade analysis; return demo string when key absent."""
    from app.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.openai_api_key:
        return _DEMO_ANALYSIS

    try:
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        prompt = (
            f"Write a 2-3 sentence trade analysis for the following filled order:\n"
            f"Symbol: {symbol}, Side: {side}, Quantity: {quantity}, "
            f"Entry Price: {entry_price}, "
            f"Sentiment Score: {sentiment_score}, "
            f"Technical Context: RSI={technical_context.get('rsi')}, "
            f"MACD Signal={technical_context.get('macd_signal')}.\n"
            "Be concise and professional."
        )
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.4,
        )
        return response.choices[0].message.content or _DEMO_ANALYSIS
    except Exception:  # noqa: BLE001
        logger.warning("journal_tasks.openai_failed", symbol=symbol)
        return _DEMO_ANALYSIS


async def _save_journal_entry(doc: dict) -> None:
    """Persist a journal entry to MongoDB trade_journal collection."""
    try:
        import motor.motor_asyncio  # noqa: PLC0415

        from app.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.mongodb_database]
        await db.trade_journal.insert_one(doc)
    except Exception:  # noqa: BLE001
        logger.warning("journal_tasks.mongodb_unavailable", order_id=doc.get("order_id"))
