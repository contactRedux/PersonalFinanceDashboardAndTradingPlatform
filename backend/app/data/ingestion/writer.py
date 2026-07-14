"""
TimescaleDB writer — persists normalized OHLCV bars.

Handles:
  - Upsert (INSERT ... ON CONFLICT UPDATE) to avoid duplicate bars
  - Batch writes for efficiency
  - Both the SQLAlchemy ORM path and raw SQL for high-throughput
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ingestion.normalizer import CanonicalBar

logger = structlog.get_logger(__name__)


async def write_bars(bars: list[CanonicalBar], db: AsyncSession) -> int:
    """
    Upsert a list of CanonicalBar records into the ohlcv table.
    Returns the number of rows written.
    """
    if not bars:
        return 0

    # Use raw SQL for batch insert performance
    upsert_sql = text("""
        INSERT INTO ohlcv (
            time, symbol, exchange, asset_class, timeframe,
            open, high, low, close, volume, vwap, trade_count, provider
        )
        VALUES (
            :time, :symbol, :exchange, :asset_class, :timeframe,
            :open, :high, :low, :close, :volume, :vwap, :trade_count, :provider
        )
        ON CONFLICT (time, symbol, timeframe)
        DO UPDATE SET
            open        = EXCLUDED.open,
            high        = EXCLUDED.high,
            low         = EXCLUDED.low,
            close       = EXCLUDED.close,
            volume      = EXCLUDED.volume,
            vwap        = EXCLUDED.vwap,
            trade_count = EXCLUDED.trade_count,
            provider    = EXCLUDED.provider
    """)

    rows = [
        {
            "time": bar.time,
            "symbol": bar.symbol,
            "exchange": bar.exchange,
            "asset_class": bar.asset_class,
            "timeframe": bar.timeframe,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "trade_count": bar.trade_count,
            "provider": bar.provider,
        }
        for bar in bars
    ]

    try:
        await db.execute(upsert_sql, rows)
        await db.commit()
        logger.debug("writer.bars.written", count=len(rows))
        return len(rows)
    except Exception:
        await db.rollback()
        logger.exception("writer.bars.error", count=len(rows))
        return 0
