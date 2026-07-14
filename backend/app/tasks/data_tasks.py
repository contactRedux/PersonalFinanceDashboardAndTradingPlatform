"""Periodic OHLCV data refresh tasks — full implementation in ST-5."""
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.refresh_ohlcv")
def refresh_ohlcv(symbol: str, timeframe: str = "1d") -> dict:
    """Fetch latest OHLCV bars and write to TimescaleDB."""
    # Implemented in ST-5
    return {"symbol": symbol, "timeframe": timeframe, "status": "pending_st5"}
