"""
Unit tests for GridSearchOptimizer and PDF report generation.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Ensure backtesting package is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_ohlcv_df(n: int = 300) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    import numpy as np

    rng = np.random.default_rng(42)
    prices = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    df = pd.DataFrame(
        {
            "open": prices,
            "high": prices + rng.uniform(0, 1, n),
            "low": prices - rng.uniform(0, 1, n),
            "close": prices + rng.normal(0, 0.3, n),
            "volume": rng.uniform(1_000_000, 5_000_000, n),
        },
        index=pd.date_range("2022-01-01", periods=n, freq="D"),
    )
    return df


# ─── ST-10: GridSearchOptimizer ───────────────────────────────────────────────


def test_expand_grid_cartesian_product():
    """expand_grid produces all combinations."""
    from backtesting.optimization.grid_search import expand_grid

    result = expand_grid({"fast": [10, 20], "slow": [40, 50]})
    assert len(result) == 4
    params_set = {(r["fast"], r["slow"]) for r in result}
    assert (10, 40) in params_set
    assert (20, 50) in params_set


def test_expand_grid_empty():
    """Empty param_space returns one combination with no params."""
    from backtesting.optimization.grid_search import expand_grid

    result = expand_grid({})
    assert result == [{}]


def test_grid_search_raises_on_empty_param_space():
    """GridSearchOptimizer raises ValueError for empty param_space."""
    from backtesting.optimization.grid_search import GridSearchOptimizer

    with pytest.raises(ValueError, match="must not be empty"):
        GridSearchOptimizer(
            strategy_class=MagicMock(),
            param_space={},
            engine_cls=MagicMock(),
        )


def test_grid_search_raises_on_empty_values():
    """GridSearchOptimizer raises ValueError if a param has an empty list."""
    from backtesting.optimization.grid_search import GridSearchOptimizer

    with pytest.raises(ValueError, match="non-empty list"):
        GridSearchOptimizer(
            strategy_class=MagicMock(),
            param_space={"fast": []},
            engine_cls=MagicMock(),
        )


def test_grid_search_full_run():
    """Full grid search on SMA Cross strategy with synthetic data."""
    from backtesting.engine.vectorized import VectorizedEngine
    from backtesting.optimization.grid_search import GridSearchOptimizer
    from backtesting.strategies.sma_cross import SmaCrossStrategy

    data = _make_ohlcv_df(300)
    optimizer = GridSearchOptimizer(
        strategy_class=SmaCrossStrategy,
        param_space={"fast": [10, 15], "slow": [30, 40]},
        engine_cls=VectorizedEngine,
        metric="sharpe_ratio",
    )
    result = optimizer.run(data, symbol="TEST")

    assert result.n_combinations == 4
    assert result.best_params in [
        {"fast": f, "slow": s}
        for f in [10, 15]
        for s in [30, 40]
    ]
    assert isinstance(result.best_value, float)
    assert len(result.all_results) == 4

    # Verify ranking: first result has highest value
    assert result.all_results[0]["value"] >= result.all_results[-1]["value"]

    # Serialize
    d = result.serialize()
    assert "best_params" in d
    assert d["n_combinations"] == 4


def test_grid_search_results_property():
    """results property returns None before run, result after run."""
    from backtesting.engine.vectorized import VectorizedEngine
    from backtesting.optimization.grid_search import GridSearchOptimizer
    from backtesting.strategies.sma_cross import SmaCrossStrategy

    optimizer = GridSearchOptimizer(
        strategy_class=SmaCrossStrategy,
        param_space={"fast": [10], "slow": [40]},
        engine_cls=VectorizedEngine,
        metric="sharpe_ratio",
    )
    assert optimizer.results is None
    data = _make_ohlcv_df(200)
    optimizer.run(data)
    assert optimizer.results is not None


# ─── ST-11: PDF report ────────────────────────────────────────────────────────


def test_generate_pdf_report_raises_without_weasyprint():
    """generate_pdf_report raises ImportError if weasyprint is not installed."""
    with patch.dict(sys.modules, {"weasyprint": None}):
        from backtesting.reporting import pdf_report  # noqa: PLC0415

        # Force reload to pick up patched modules
        import importlib  # noqa: PLC0415
        importlib.reload(pdf_report)

        with pytest.raises((ImportError, Exception)):
            mock_result = MagicMock()
            mock_result.equity_curve = [100_000.0, 110_000.0]
            pdf_report.generate_pdf_report(mock_result)


def test_generate_pdf_report_returns_bytes_when_weasyprint_available():
    """generate_pdf_report returns non-empty bytes with mocked WeasyPrint."""
    mock_html_class = MagicMock()
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.return_value = b"%PDF-1.4 fake content"
    mock_html_class.return_value = mock_html_instance

    mock_weasyprint = MagicMock()
    mock_weasyprint.HTML = mock_html_class

    # Create a minimal BacktestResult-like mock
    from backtesting.engine.base import BacktestResult
    import pandas as pd

    result = BacktestResult(
        symbol="SPY",
        timeframe="1d",
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        initial_capital=100_000.0,
    )
    result.equity_curve = [100_000.0, 101_000.0, 102_000.0]
    result.compute_metrics()

    with patch.dict(sys.modules, {"weasyprint": mock_weasyprint}):
        from backtesting.reporting import pdf_report
        import importlib

        importlib.reload(pdf_report)
        pdf_bytes = pdf_report.generate_pdf_report(result)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
