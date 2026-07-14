"""
Periodic OHLCV data refresh tasks and tick data recorder.

ST-U: record_ticks() connects to the Alpaca WebSocket stream and stores
tick data to TimescaleDB.  When Alpaca keys are absent it is a no-op.
"""

from __future__ import annotations

import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="tasks.refresh_ohlcv")
def refresh_ohlcv(symbol: str, timeframe: str = "1d") -> dict:
    """Fetch latest OHLCV bars and write to TimescaleDB."""
    # Implemented in ST-5
    return {"symbol": symbol, "timeframe": timeframe, "status": "pending_st5"}


@celery_app.task(name="tasks.record_ticks", max_retries=0)
def record_ticks() -> dict:
    """
    Connect to Alpaca WebSocket, subscribe to trades for TICK_SYMBOLS, and
    persist each tick to the TimescaleDB ``ticks`` table.

    Returns when the connection closes or when Alpaca keys are absent.
    """
    try:
        return asyncio.run(_record_ticks_async())
    except Exception:  # noqa: BLE001
        logger.exception("tasks.record_ticks.error")
        return {"status": "error"}


async def _record_ticks_async() -> dict:
    """Async implementation — runs inside asyncio.run() from the sync Celery task."""
    from app.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    if not settings.alpaca_api_key or not (
        settings.alpaca_api_secret or settings.alpaca_secret_key
    ):
        logger.debug("tasks.record_ticks.skipped", reason="no_alpaca_keys")
        return {"status": "skipped", "reason": "no_alpaca_keys"}

    import json  # noqa: PLC0415
    import os  # noqa: PLC0415

    try:
        import websockets  # noqa: PLC0415
    except ImportError:
        logger.debug("tasks.record_ticks.skipped", reason="websockets_not_installed")
        return {"status": "skipped", "reason": "websockets_not_installed"}

    secret = settings.alpaca_api_secret or settings.alpaca_secret_key
    symbols_env = os.environ.get("TICK_SYMBOLS", "AAPL,MSFT,TSLA")
    symbols: list[str] = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]

    ws_url = "wss://stream.data.alpaca.markets/v2/iex"

    ticks_stored = 0
    try:
        async with websockets.connect(ws_url) as ws:
            # Authenticate
            await ws.send(
                json.dumps(
                    {
                        "action": "auth",
                        "key": settings.alpaca_api_key,
                        "secret": secret,
                    }
                )
            )

            # Subscribe to trades
            await ws.send(
                json.dumps({"action": "subscribe", "trades": symbols})
            )

            async for raw in ws:
                messages = json.loads(raw)
                if not isinstance(messages, list):
                    messages = [messages]
                for msg in messages:
                    if msg.get("T") == "t":  # trade message
                        await _store_tick(msg)
                        ticks_stored += 1
    except Exception:  # noqa: BLE001
        logger.exception("tasks.record_ticks.ws_error")

    return {"status": "done", "ticks_stored": ticks_stored}


async def _store_tick(msg: dict) -> None:
    """Persist a single trade tick to the ``ticks`` table (or log in demo mode)."""
    tick = {
        "symbol": msg.get("S", ""),
        "price": float(msg.get("p", 0)),
        "size": int(msg.get("s", 0)),
        "timestamp": msg.get("t", ""),
        "exchange": msg.get("x", ""),
        "conditions": msg.get("c", []),
    }
    try:
        from app.database import AsyncSessionLocal  # noqa: PLC0415

        async with AsyncSessionLocal() as session:
            await session.execute(
                # Raw INSERT — ticks table managed by TimescaleDB DDL outside Alembic
                __import__("sqlalchemy").text(
                    "INSERT INTO ticks (symbol, price, size, ts, exchange, conditions)"
                    " VALUES (:symbol, :price, :size, :ts, :exchange, :conditions)"
                    " ON CONFLICT DO NOTHING"
                ),
                {
                    "symbol": tick["symbol"],
                    "price": tick["price"],
                    "size": tick["size"],
                    "ts": tick["timestamp"],
                    "exchange": tick["exchange"],
                    "conditions": str(tick["conditions"]),
                },
            )
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.debug("tasks.record_ticks.store_skipped", tick_symbol=tick["symbol"])
