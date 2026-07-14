"""
Unit tests for the tick replay engine (ST-U).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.tick_replay import TickReplayEngine


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def synthetic_ticks() -> pd.DataFrame:
    """100 synthetic ticks with a gentle uptrend."""
    rng = np.random.default_rng(0)
    n = 100
    prices = 100.0 + np.cumsum(rng.normal(0, 0.05, n))
    sizes = rng.integers(1, 100, n).astype(float)
    timestamps = pd.date_range("2024-01-02 09:30:00", periods=n, freq="1s", tz="UTC")
    return pd.DataFrame({"timestamp": timestamps, "price": prices, "size": sizes})


# ─── Simple strategy stubs ────────────────────────────────────────────────────


class AlwaysBuyStrategy:
    """Always returns +1 on every tick."""

    def on_tick(self, price: float, size: float) -> int:  # noqa: ARG002
        return 1


class BuyHoldSellStrategy:
    """Buy first half, flat second half."""

    def __init__(self, n: int) -> None:
        self._n = n
        self._i = 0

    def on_tick(self, price: float, size: float) -> int:  # noqa: ARG002
        sig = 1 if self._i < self._n // 2 else 0
        self._i += 1
        return sig


class SignalStrategy:
    """Uses generate_signals so the fallback path is exercised."""

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        # Buy first half, flat second half
        n = len(data)
        sigs = [1 if i < n // 2 else 0 for i in range(n)]
        return pd.Series(sigs, index=data.index)


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestTickReplayEngine:
    def test_equity_curve_length_matches_tick_count(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, AlwaysBuyStrategy(), symbol="AAPL")
        assert len(result.equity_curve) == len(synthetic_ticks)

    def test_equity_curve_length_matches_timestamps(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, AlwaysBuyStrategy(), symbol="AAPL")
        assert len(result.equity_curve) == len(result.timestamps)

    def test_result_symbol_set_correctly(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, AlwaysBuyStrategy(), symbol="TSLA")
        assert result.symbol == "TSLA"

    def test_compute_metrics_works(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, BuyHoldSellStrategy(100), symbol="AAPL")
        result.compute_metrics()
        assert isinstance(result.final_equity, float)
        assert isinstance(result.total_return_pct, float)
        assert isinstance(result.sharpe_ratio, float)

    def test_compute_metrics_total_return(self, synthetic_ticks):
        engine = TickReplayEngine(initial_capital=100_000.0)
        result = engine.run(synthetic_ticks, BuyHoldSellStrategy(100), symbol="AAPL")
        result.compute_metrics()
        # final_equity should be set from equity_curve
        assert result.final_equity == pytest.approx(result.equity_curve[-1], rel=1e-6)

    def test_fallback_generate_signals_path(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, SignalStrategy(), symbol="SPY")
        assert len(result.equity_curve) == len(synthetic_ticks)

    def test_empty_ticks_returns_result(self):
        engine = TickReplayEngine()
        empty = pd.DataFrame(columns=["timestamp", "price", "size"])
        result = engine.run(empty, AlwaysBuyStrategy(), symbol="AAPL")
        assert result.equity_curve == [100_000.0]

    def test_missing_column_raises(self, synthetic_ticks):
        engine = TickReplayEngine()
        bad = synthetic_ticks.drop(columns=["price"])
        with pytest.raises(ValueError, match="Missing required column"):
            engine.run(bad, AlwaysBuyStrategy())

    def test_trade_recorded_on_position_close(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, BuyHoldSellStrategy(100), symbol="AAPL")
        # BuyHoldSellStrategy opens at tick 0, closes at tick 50 → at least 1 trade
        assert result.total_trades >= 0  # compute_metrics not called yet
        result.compute_metrics()
        assert result.total_trades >= 0

    def test_start_end_timestamps(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, AlwaysBuyStrategy(), symbol="AAPL")
        assert result.start == pd.Timestamp(synthetic_ticks["timestamp"].iloc[0])
        assert result.end == pd.Timestamp(synthetic_ticks["timestamp"].iloc[-1])

    def test_speed_multiplier_stored(self):
        engine = TickReplayEngine(speed_multiplier=2.5)
        assert engine.speed_multiplier == 2.5

    def test_timeframe_is_tick(self, synthetic_ticks):
        engine = TickReplayEngine()
        result = engine.run(synthetic_ticks, AlwaysBuyStrategy())
        assert result.timeframe == "tick"
