"""
Walk-Forward Optimizer.

Splits the data into anchored in-sample / out-of-sample windows,
optimises strategy parameters in-sample (grid search), then evaluates
on the unseen out-of-sample window. Returns per-fold results and
aggregate out-of-sample equity curve.

Example::

    from backtesting.optimization.walk_forward import WalkForwardOptimizer
    from backtesting.strategies.sma_cross import SmaCrossStrategy
    from backtesting.engine.vectorized import VectorizedEngine

    optimizer = WalkForwardOptimizer(
        engine_cls=VectorizedEngine,
        param_grid={"fast": [10, 20], "slow": [40, 50, 60]},
        in_sample_bars=252,
        out_of_sample_bars=63,
        metric="sharpe_ratio",
        maximize=True,
    )
    folds = optimizer.run(data, SmaCrossStrategy, symbol="AAPL")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any

import pandas as pd

from backtesting.engine.base import BacktestResult


@dataclass
class WalkForwardFold:
    """Result for a single walk-forward window."""

    fold: int
    in_sample_start: pd.Timestamp
    in_sample_end: pd.Timestamp
    out_of_sample_start: pd.Timestamp
    out_of_sample_end: pd.Timestamp
    best_params: dict[str, Any]
    in_sample_metric: float
    out_of_sample_result: BacktestResult


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward optimization results."""

    folds: list[WalkForwardFold] = field(default_factory=list)
    combined_equity: list[float] = field(default_factory=list)
    combined_timestamps: list[pd.Timestamp] = field(default_factory=list)
    avg_oos_sharpe: float = 0.0
    avg_oos_return: float = 0.0
    total_oos_trades: int = 0

    def aggregate(self) -> None:
        """Combine OOS equity curves and compute summary stats."""
        for fold in self.folds:
            r = fold.out_of_sample_result
            r.compute_metrics()
            self.combined_equity.extend(r.equity_curve)
            self.combined_timestamps.extend(r.timestamps)
        sharpe_vals = [f.out_of_sample_result.sharpe_ratio for f in self.folds]
        ret_vals = [f.out_of_sample_result.total_return_pct for f in self.folds]
        self.avg_oos_sharpe = sum(sharpe_vals) / len(sharpe_vals) if sharpe_vals else 0.0
        self.avg_oos_return = sum(ret_vals) / len(ret_vals) if ret_vals else 0.0
        self.total_oos_trades = sum(
            f.out_of_sample_result.total_trades for f in self.folds
        )


def _expand_grid(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of param_grid values."""
    keys = list(param_grid.keys())
    combos = list(product(*param_grid.values()))
    return [dict(zip(keys, combo)) for combo in combos]


class WalkForwardOptimizer:
    """
    Anchored walk-forward optimizer.

    Parameters
    ----------
    engine_cls : type
        A VectorizedEngine or EventDrivenEngine class (not instance).
    param_grid : dict
        Mapping of parameter name → list of values to try.
    in_sample_bars : int
        Number of bars in each in-sample window.
    out_of_sample_bars : int
        Number of bars in each out-of-sample window.
    metric : str
        Metric attribute on BacktestResult to optimise.
    maximize : bool
        True = maximise metric (e.g. Sharpe). False = minimise.
    engine_kwargs : dict
        Keyword arguments forwarded to the engine constructor.
    """

    def __init__(
        self,
        engine_cls: type,
        param_grid: dict[str, list[Any]],
        in_sample_bars: int = 252,
        out_of_sample_bars: int = 63,
        metric: str = "sharpe_ratio",
        maximize: bool = True,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.engine_cls = engine_cls
        self.param_grid = param_grid
        self.in_sample_bars = in_sample_bars
        self.out_of_sample_bars = out_of_sample_bars
        self.metric = metric
        self.maximize = maximize
        self.engine_kwargs = engine_kwargs or {}

    def run(
        self,
        data: pd.DataFrame,
        strategy_cls: type,
        symbol: str = "UNKNOWN",
        timeframe: str = "1d",
    ) -> WalkForwardResult:
        """Run walk-forward optimization over ``data``."""
        combos = _expand_grid(self.param_grid)
        wf_result = WalkForwardResult()
        fold_num = 0
        start_idx = 0

        while start_idx + self.in_sample_bars + self.out_of_sample_bars <= len(data):
            is_end = start_idx + self.in_sample_bars
            oos_end = is_end + self.out_of_sample_bars
            is_data = data.iloc[start_idx:is_end]
            oos_data = data.iloc[is_end:oos_end]

            # Grid search on in-sample
            best_params: dict[str, Any] = combos[0]
            best_metric: float = float("-inf") if self.maximize else float("inf")
            for params in combos:
                try:
                    strategy = strategy_cls(**params)
                    engine = self.engine_cls(**self.engine_kwargs)
                    result = engine.run(is_data, strategy, symbol=symbol, timeframe=timeframe)
                    result.compute_metrics()
                    val = float(getattr(result, self.metric, 0.0))
                    if (self.maximize and val > best_metric) or (
                        not self.maximize and val < best_metric
                    ):
                        best_metric = val
                        best_params = params
                except Exception:  # noqa: BLE001
                    continue

            # Evaluate best params on OOS
            best_strategy = strategy_cls(**best_params)
            engine = self.engine_cls(**self.engine_kwargs)
            oos_result = engine.run(oos_data, best_strategy, symbol=symbol, timeframe=timeframe)

            wf_result.folds.append(
                WalkForwardFold(
                    fold=fold_num,
                    in_sample_start=pd.Timestamp(is_data.index[0]),
                    in_sample_end=pd.Timestamp(is_data.index[-1]),
                    out_of_sample_start=pd.Timestamp(oos_data.index[0]),
                    out_of_sample_end=pd.Timestamp(oos_data.index[-1]),
                    best_params=best_params,
                    in_sample_metric=best_metric,
                    out_of_sample_result=oos_result,
                )
            )
            fold_num += 1
            start_idx += self.out_of_sample_bars  # roll forward by OOS window

        wf_result.aggregate()
        return wf_result
