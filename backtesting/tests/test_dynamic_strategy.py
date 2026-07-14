"""
Unit tests for DynamicStrategy (ST-L).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def sample_data() -> pd.DataFrame:
    """200 bars of synthetic OHLCV data."""
    rng = np.random.default_rng(7)
    n = 200
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    opens = close + rng.normal(0, 0.2, n)
    volume = rng.integers(10000, 100000, n).astype(float)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": opens, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


class TestDynamicStrategyValidation:
    def test_missing_nodes_raises(self) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        with pytest.raises(ValueError, match="nodes"):
            DynamicStrategy({"edges": []})

    def test_missing_edges_raises(self) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        with pytest.raises(ValueError, match="edges"):
            DynamicStrategy({"nodes": []})

    def test_valid_config_constructs(self) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        ds = DynamicStrategy({"nodes": [], "edges": []})
        assert ds is not None


class TestDynamicStrategyRSIBuy:
    """RSI < 30 → BUY graph."""

    @pytest.fixture()
    def rsi_config(self) -> dict:
        return {
            "nodes": [
                {"id": "n-rsi", "type": "indicator", "data": {"indicator": "rsi", "period": "14"}},
                {"id": "n-lt", "type": "comparator", "data": {"op": "lt", "value": "30"}},
                {"id": "n-buy", "type": "entry", "data": {"side": "buy"}},
            ],
            "edges": [
                {"source": "n-rsi", "target": "n-lt"},
                {"source": "n-lt", "target": "n-buy"},
            ],
        }

    def test_signals_length_matches_data(self, sample_data: pd.DataFrame, rsi_config: dict) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        ds = DynamicStrategy(rsi_config)
        signals = ds.generate_signals(sample_data)
        assert len(signals) == len(sample_data)

    def test_signals_only_1_0(self, sample_data: pd.DataFrame, rsi_config: dict) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        ds = DynamicStrategy(rsi_config)
        signals = ds.generate_signals(sample_data)
        assert set(signals.unique()).issubset({0.0, 1.0})

    def test_buy_signals_when_rsi_below_threshold(
        self, sample_data: pd.DataFrame, rsi_config: dict
    ) -> None:
        """Signal must be 1 on bars where RSI < 30."""
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415
        from backtesting.strategies.dynamic import _compute_indicator  # noqa: PLC0415

        ds = DynamicStrategy(rsi_config)
        signals = ds.generate_signals(sample_data)
        rsi = _compute_indicator(sample_data, {"indicator": "rsi", "period": "14"})
        # On bars where RSI < 30, signal must be 1
        mask = rsi < 30
        assert (signals[mask] == 1.0).all()


class TestDynamicStrategySMABuy:
    """SMA crosses above price → BUY."""

    def test_sma_indicator_produces_series(self, sample_data: pd.DataFrame) -> None:
        from backtesting.strategies.dynamic import _compute_indicator  # noqa: PLC0415

        result = _compute_indicator(sample_data, {"indicator": "sma", "period": "20"})
        assert len(result) == len(sample_data)
        assert result.iloc[20:].notna().all()

    def test_ema_indicator_produces_series(self, sample_data: pd.DataFrame) -> None:
        from backtesting.strategies.dynamic import _compute_indicator  # noqa: PLC0415

        result = _compute_indicator(sample_data, {"indicator": "ema", "period": "20"})
        assert len(result) == len(sample_data)

    def test_empty_graph_returns_zeros(self, sample_data: pd.DataFrame) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        ds = DynamicStrategy({"nodes": [], "edges": []})
        signals = ds.generate_signals(sample_data)
        assert (signals == 0).all()

    def test_entry_without_parent_returns_zeros(self, sample_data: pd.DataFrame) -> None:
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        ds = DynamicStrategy({"nodes": [{"id": "e", "type": "entry", "data": {"side": "buy"}}], "edges": []})
        signals = ds.generate_signals(sample_data)
        assert (signals == 0).all()


class TestDynamicStrategyRunsInEngine:
    def test_runs_in_vectorized_engine(self, sample_data: pd.DataFrame) -> None:
        from backtesting.engine.vectorized import VectorizedEngine  # noqa: PLC0415
        from backtesting.strategies.dynamic import DynamicStrategy  # noqa: PLC0415

        config = {
            "nodes": [
                {"id": "n1", "type": "indicator", "data": {"indicator": "rsi", "period": "14"}},
                {"id": "n2", "type": "comparator", "data": {"op": "lt", "value": "40"}},
                {"id": "n3", "type": "entry", "data": {"side": "buy"}},
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        }
        ds = DynamicStrategy(config)
        engine = VectorizedEngine()
        result = engine.run(sample_data, ds, symbol="TEST")
        result.compute_metrics()
        assert hasattr(result, "total_trades")
        assert hasattr(result, "sharpe_ratio")
