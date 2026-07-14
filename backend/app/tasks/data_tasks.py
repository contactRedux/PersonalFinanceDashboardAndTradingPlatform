"""
Periodic OHLCV data refresh tasks and tick data recorder.

Tasks:
  refresh_ohlcv — fetch bars from Alpaca (yfinance fallback), write to TimescaleDB,
                  notify WebSocket clients on completion.
  record_ticks  — connect to Alpaca WebSocket, buffer ticks, batch-flush to TimescaleDB.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import structlog

from app.tasks.celery_app import celery_app

# ─── Lazily-resolved dependencies (patchable in tests) ────────────────────────
# These are resolved at call time; defining them here makes `patch(...)` work.

def get_provider():  # type: ignore[return]
    """Return the configured market data provider singleton."""
    from app.services.market_data.router import get_provider as _gp  # noqa: PLC0415
    return _gp()


async def write_bars(bars, session):  # type: ignore[return]
    """Write canonical bars to TimescaleDB."""
    from app.data.ingestion.writer import write_bars as _wb  # noqa: PLC0415
    return await _wb(bars, session)


async def publish(channel: str, payload: dict) -> None:
    """Publish a message to a Redis pub/sub channel."""
    from app.data.cache.pubsub import publish as _pub  # noqa: PLC0415
    await _pub(channel, payload)


def _get_session_local():
    from app.database import AsyncSessionLocal as _asl  # noqa: PLC0415
    return _asl


# Patchable alias so tests can do: patch("app.tasks.data_tasks.AsyncSessionLocal", ...)
try:
    from app.database import AsyncSessionLocal  # noqa: PLC0415
except Exception:  # noqa: BLE001
    AsyncSessionLocal = _get_session_local  # type: ignore[assignment, misc]

logger = structlog.get_logger(__name__)

# ─── Prometheus metrics (optional — only if prometheus_client is importable) ──

try:
    from prometheus_client import Counter, Histogram

    _TICKS_STORED = Counter(
        "ticks_stored_total",
        "Number of tick records written to TimescaleDB",
        ["symbol"],
    )
    _TICK_BATCH_SIZE = Histogram(
        "tick_batch_size",
        "Number of ticks per batch flush",
        buckets=[10, 50, 100, 250, 500, 1000],
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


# ─── ST-4: refresh_ohlcv ──────────────────────────────────────────────────────


@celery_app.task(
    name="tasks.refresh_ohlcv",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def refresh_ohlcv(self, symbol: str, timeframe: str = "1d") -> dict:
    """Fetch latest OHLCV bars and write to TimescaleDB."""
    try:
        return asyncio.run(_refresh_ohlcv_async(symbol, timeframe))
    except Exception as exc:  # noqa: BLE001
        backoff = 5 * (2 ** self.request.retries)
        logger.warning(
            "tasks.refresh_ohlcv.retry",
            symbol=symbol,
            retry=self.request.retries,
            backoff=backoff,
        )
        try:
            raise self.retry(exc=exc, countdown=backoff)
        except self.MaxRetriesExceededError:
            logger.error(
                "tasks.refresh_ohlcv.dead_letter",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            return {"symbol": symbol, "timeframe": timeframe, "status": "failed", "error": str(exc)}


async def _refresh_ohlcv_async(symbol: str, timeframe: str) -> dict:
    """Fetch bars and write them to TimescaleDB."""
    # Uses module-level wrappers (get_provider, write_bars, publish, AsyncSessionLocal)
    # so that unit tests can patch them at 'app.tasks.data_tasks.*'
    provider = get_provider()

    # Fetch last 365 days by default
    end = datetime.now(UTC).date().isoformat()
    start_dt = (datetime.now(UTC).date() - timedelta(days=365)).isoformat()

    bars = await provider.get_bars(symbol, timeframe, start=start_dt, end=end, limit=500)

    bars_written = 0
    if bars:
        # AsyncSessionLocal is a module-level patchable alias
        async with AsyncSessionLocal() as session:
            bars_written = await write_bars(bars, session)

    # Notify WebSocket clients
    try:
        await publish(
            f"channel:market:{symbol.upper()}",
            {
                "type": "ohlcv_refreshed",
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "bars_written": bars_written,
                "as_of": datetime.now(UTC).isoformat(),
            },
        )
    except Exception:  # noqa: BLE001
        logger.debug("tasks.refresh_ohlcv.publish_skipped", symbol=symbol)

    logger.info("tasks.refresh_ohlcv.done", symbol=symbol, timeframe=timeframe, bars_written=bars_written)
    return {"symbol": symbol, "timeframe": timeframe, "bars_written": bars_written, "status": "ok"}


# ─── ST-5: record_ticks ───────────────────────────────────────────────────────


class _TickBatcher:
    """
    In-memory tick buffer with configurable flush triggers.

    Flushes when:
      - buffer reaches max_size (default 500)
      - max_age_seconds have elapsed since last flush (default 1.0)
    """

    def __init__(self, max_size: int = 500, max_age_seconds: float = 1.0) -> None:
        self._buffer: list[dict] = []
        self._max_size = max_size
        self._max_age = max_age_seconds
        self._last_flush: float = time.monotonic()
        self._total_flushed = 0

    def _should_flush(self) -> bool:
        return len(self._buffer) >= self._max_size or (
            time.monotonic() - self._last_flush >= self._max_age and len(self._buffer) > 0
        )

    async def add(self, tick: dict) -> None:
        self._buffer.append(tick)
        if self._should_flush():
            await self.flush()

    async def flush(self) -> int:
        if not self._buffer:
            return 0
        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush = time.monotonic()
        n = await _batch_write_ticks(batch)
        self._total_flushed += n
        if _PROMETHEUS_AVAILABLE:
            _TICK_BATCH_SIZE.observe(len(batch))
        return n

    @property
    def total_flushed(self) -> int:
        return self._total_flushed


async def _batch_write_ticks(ticks: list[dict]) -> int:
    """Insert a batch of ticks into TimescaleDB using the ORM tick schema."""
    if not ticks:
        return 0
    try:
        import sqlalchemy as sa  # noqa: PLC0415

        from app.database import AsyncSessionLocal  # noqa: PLC0415

        # Match the ticks table DDL: (time, symbol, price, size, side, exchange, provider)
        sql = sa.text(
            "INSERT INTO ticks (time, symbol, price, size, side, exchange, provider)"
            " VALUES (:time, :symbol, :price, :size, :side, :exchange, :provider)"
            " ON CONFLICT DO NOTHING"
        )

        rows = [
            {
                "time": t.get("timestamp") or datetime.now(UTC).isoformat(),
                "symbol": t["symbol"],
                "price": t["price"],
                "size": t["size"],
                "side": None,  # Alpaca trade messages don't carry side
                "exchange": t.get("exchange", ""),
                "provider": "alpaca",
            }
            for t in ticks
            if t.get("symbol") and t.get("price")
        ]
        if not rows:
            return 0

        async with AsyncSessionLocal() as session:
            await session.execute(sql, rows)
            await session.commit()

        if _PROMETHEUS_AVAILABLE:
            from collections import Counter as PyCounter  # noqa: PLC0415

            symbol_counts = PyCounter(r["symbol"] for r in rows)
            for sym, cnt in symbol_counts.items():
                _TICKS_STORED.labels(symbol=sym).inc(cnt)

        return len(rows)
    except Exception:  # noqa: BLE001
        logger.debug("tasks.record_ticks.batch_write_failed", count=len(ticks))
        return 0


@celery_app.task(name="tasks.record_ticks", max_retries=0)
def record_ticks() -> dict:
    """
    Connect to Alpaca WebSocket, subscribe to trades for TICK_SYMBOLS, and
    persist each tick to the TimescaleDB ``ticks`` table using batched inserts.

    Returns when the connection closes or when Alpaca keys are absent.
    """
    try:
        return asyncio.run(_record_ticks_async())
    except Exception:  # noqa: BLE001
        logger.exception("tasks.record_ticks.error")
        return {"status": "error"}


async def _record_ticks_async() -> dict:
    """Async implementation — runs inside asyncio.run() from the sync Celery task."""
    import json  # noqa: PLC0415
    import os  # noqa: PLC0415

    from app.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    if not settings.alpaca_api_key or not (
        settings.alpaca_api_secret or settings.alpaca_secret_key
    ):
        logger.debug("tasks.record_ticks.skipped", reason="no_alpaca_keys")
        return {"status": "skipped", "reason": "no_alpaca_keys"}

    try:
        import websockets  # noqa: PLC0415
    except ImportError:
        logger.debug("tasks.record_ticks.skipped", reason="websockets_not_installed")
        return {"status": "skipped", "reason": "websockets_not_installed"}

    secret = settings.alpaca_api_secret or settings.alpaca_secret_key
    symbols_env = os.environ.get("TICK_SYMBOLS", "AAPL,MSFT,TSLA")
    symbols: list[str] = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]
    max_size = int(os.environ.get("TICK_BATCH_SIZE", "500"))
    max_age = float(os.environ.get("TICK_BATCH_AGE_S", "1.0"))

    batcher = _TickBatcher(max_size=max_size, max_age_seconds=max_age)
    ws_url = "wss://stream.data.alpaca.markets/v2/iex"

    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(
                json.dumps({
                    "action": "auth",
                    "key": settings.alpaca_api_key,
                    "secret": secret,
                })
            )
            await ws.send(json.dumps({"action": "subscribe", "trades": symbols}))

            async for raw in ws:
                messages = json.loads(raw)
                if not isinstance(messages, list):
                    messages = [messages]
                for msg in messages:
                    if msg.get("T") == "t":  # trade message
                        tick = {
                            "symbol": msg.get("S", ""),
                            "price": float(msg.get("p", 0)),
                            "size": int(msg.get("s", 0)),
                            "timestamp": msg.get("t", ""),
                            "exchange": msg.get("x", ""),
                        }
                        await batcher.add(tick)

    except Exception:  # noqa: BLE001
        logger.exception("tasks.record_ticks.ws_error")
    finally:
        # Flush any remaining buffered ticks
        await batcher.flush()

    return {"status": "done", "ticks_stored": batcher.total_flushed}
