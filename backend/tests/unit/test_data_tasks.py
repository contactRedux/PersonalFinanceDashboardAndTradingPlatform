"""
Unit tests for ST-4 (refresh_ohlcv) and ST-5 (_TickBatcher) data tasks.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── ST-4: refresh_ohlcv ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_refresh_ohlcv_async_calls_provider_and_writer():
    """refresh_ohlcv fetches bars and writes them via write_bars."""
    from datetime import UTC, datetime  # noqa: PLC0415

    from app.data.ingestion.normalizer import CanonicalBar  # noqa: PLC0415

    fake_bar = CanonicalBar(
        time=datetime.now(UTC),
        symbol="SPY",
        exchange="NYSE",
        asset_class="equity",
        timeframe="1d",
        open=400.0,
        high=405.0,
        low=398.0,
        close=403.0,
        volume=50_000_000.0,
        provider="yfinance",
    )
    mock_provider = MagicMock()
    mock_provider.get_bars = AsyncMock(return_value=[fake_bar])

    mock_write = AsyncMock(return_value=1)
    mock_publish = AsyncMock()

    # Patch the session context manager
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.data_tasks.get_provider", return_value=mock_provider),
        patch("app.tasks.data_tasks.write_bars", mock_write),
        patch("app.tasks.data_tasks.AsyncSessionLocal", return_value=mock_session),
        patch("app.tasks.data_tasks.publish", mock_publish),
    ):
        from app.tasks.data_tasks import _refresh_ohlcv_async  # noqa: PLC0415

        result = await _refresh_ohlcv_async("SPY", "1d")

    assert result["status"] == "ok"
    assert result["bars_written"] == 1
    assert result["symbol"] == "SPY"


@pytest.mark.anyio
async def test_refresh_ohlcv_fallback_on_empty_bars():
    """When provider returns no bars, task completes with bars_written=0."""
    mock_provider = MagicMock()
    mock_provider.get_bars = AsyncMock(return_value=[])
    mock_publish = AsyncMock()

    with (
        patch("app.tasks.data_tasks.get_provider", return_value=mock_provider),
        patch("app.tasks.data_tasks.publish", mock_publish),
    ):
        from app.tasks.data_tasks import _refresh_ohlcv_async  # noqa: PLC0415

        result = await _refresh_ohlcv_async("AAPL", "1d")

    assert result["status"] == "ok"
    assert result["bars_written"] == 0


# ─── ST-5: _TickBatcher ───────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_tick_batcher_flushes_at_max_size():
    """Batcher flushes automatically when buffer hits max_size."""
    from app.tasks.data_tasks import _TickBatcher  # noqa: PLC0415

    flushed_batches: list[list[dict]] = []

    async def mock_batch_write(ticks: list[dict]) -> int:
        flushed_batches.append(ticks[:])
        return len(ticks)

    with patch("app.tasks.data_tasks._batch_write_ticks", side_effect=mock_batch_write):
        batcher = _TickBatcher(max_size=5, max_age_seconds=60.0)
        for i in range(5):
            await batcher.add({"symbol": "AAPL", "price": 100.0 + i, "size": 100, "timestamp": ""})

    assert len(flushed_batches) == 1
    assert len(flushed_batches[0]) == 5


@pytest.mark.anyio
async def test_tick_batcher_flushes_at_age_timeout():
    """Batcher flushes when max_age_seconds elapses even if buffer not full."""
    from app.tasks.data_tasks import _TickBatcher  # noqa: PLC0415

    flushed_batches: list[list[dict]] = []

    async def mock_batch_write(ticks: list[dict]) -> int:
        flushed_batches.append(ticks[:])
        return len(ticks)

    with patch("app.tasks.data_tasks._batch_write_ticks", side_effect=mock_batch_write):
        batcher = _TickBatcher(max_size=500, max_age_seconds=0.01)
        await batcher.add({"symbol": "MSFT", "price": 300.0, "size": 10, "timestamp": ""})

        # Wait for the age window to pass
        await asyncio.sleep(0.05)

        # Adding another tick triggers age-based flush
        await batcher.add({"symbol": "MSFT", "price": 301.0, "size": 10, "timestamp": ""})

    assert len(flushed_batches) >= 1


@pytest.mark.anyio
async def test_tick_batcher_explicit_flush():
    """Manual flush writes all buffered ticks."""
    from app.tasks.data_tasks import _TickBatcher  # noqa: PLC0415

    written: list[int] = []

    async def mock_batch_write(ticks: list[dict]) -> int:
        written.append(len(ticks))
        return len(ticks)

    with patch("app.tasks.data_tasks._batch_write_ticks", side_effect=mock_batch_write):
        batcher = _TickBatcher(max_size=500, max_age_seconds=60.0)
        for i in range(3):
            # Use a very large max_size to prevent auto-flush
            batcher._buffer.append({"symbol": "TSLA", "price": 200.0, "size": 1, "timestamp": ""})
        await batcher.flush()

    assert sum(written) == 3
    assert batcher.total_flushed == 3
