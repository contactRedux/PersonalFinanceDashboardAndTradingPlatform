"""
APScheduler-based data ingestion scheduler.

Jobs:
  - Refresh OHLCV bars for watchlisted symbols every minute (intraday)
  - Refresh daily bars every hour
  - Publish latest quotes to Redis every 15 seconds

This runs as a background task launched from the FastAPI lifespan context.
"""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.data.cache.pubsub import publish
from app.data.cache.quote_cache import set_quote
from app.services.market_data.router import get_provider

logger = structlog.get_logger(__name__)
settings = get_settings()

# Default symbols to always keep fresh (can be expanded from watchlists in DB)
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "BTC-USD", "ETH-USD"]


async def _refresh_quotes() -> None:
    """Fetch latest quotes for default symbols and publish to Redis."""
    provider = get_provider()
    symbols = DEFAULT_SYMBOLS
    try:
        quotes = await provider.get_quotes(symbols)
        for sym, quote in quotes.items():
            if quote is None:
                continue
            quote_dict = quote.to_dict()
            await set_quote(sym, quote_dict)
            await publish(f"channel:quotes:{sym}", {"type": "quote", **quote_dict})
            await publish("channel:quotes", {"type": "quote", **quote_dict})
        logger.debug("scheduler.quotes.refreshed", count=len(quotes))
    except Exception:
        logger.exception("scheduler.quotes.error")


async def _refresh_daily_bars() -> None:
    """Refresh daily bars for default symbols and write to TimescaleDB."""
    from app.database import AsyncSessionLocal

    provider = get_provider()
    symbols = DEFAULT_SYMBOLS

    async with AsyncSessionLocal() as db:
        from app.data.ingestion.writer import write_bars

        written_total = 0
        for sym in symbols:
            try:
                bars = await provider.get_bars(sym, "1d", limit=30)
                written = await write_bars(bars, db)
                written_total += written
            except Exception:
                logger.exception("scheduler.daily_bars.error", symbol=sym)

        logger.info("scheduler.daily_bars.done", written=written_total)


_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler instance."""
    global _scheduler

    scheduler = AsyncIOScheduler()

    # Quote refresh: every 15 seconds
    scheduler.add_job(
        _refresh_quotes,
        trigger=IntervalTrigger(seconds=15),
        id="refresh_quotes",
        replace_existing=True,
        max_instances=1,
    )

    # Daily bar refresh: every 30 minutes
    scheduler.add_job(
        _refresh_daily_bars,
        trigger=IntervalTrigger(minutes=30),
        id="refresh_daily_bars",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler.started", jobs=len(scheduler.get_jobs()))
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler.stopped")
