"""
Grid Search Optimizer — standalone exhaustive parameter search.

Evaluates every combination of parameters from the supplied grid,
ranks results by the target metric, and returns the best configuration.

Implements the same interface as BayesianOptimizer:
  - __init__(strategy_class, param_space, engine_cls, metric, maximize, engine_kwargs)
  - run(data, symbol, timeframe) → GridSearchResult
  - results property → GridSearchResult (after run)
  - serialize() → JSON-serializable dict

Example::

    from backtesting.optimization.grid_search import GridSearchOptimizer
    from backtesting.strategies.sma_cross import SmaCrossStrategy
    from backtesting.engine.vectorized import VectorizedEngine

    opt = GridSearchOptimizer(
        strategy_class=SmaCrossStrategy,
        param_space={"fast": [10, 20, 30], "slow": [40, 50, 60]},
        engine_cls=VectorizedEngine,
        metric="sharpe_ratio",
    )
    result = opt.run(data, symbol="AAPL")
    print(result.best_params, result.best_value)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any

import pandas as pd

from backtesting.engine.base import BacktestResult


@dataclass
class GridSearchResult:
    """Results from a grid search optimisation run."""

    best_params: dict[str, Any]
    best_value: float
    metric: str
    n_combinations: int
    # All evaluated combinations, ranked best → worst
    all_results: list[dict[str, Any]] = field(default_factory=list)

    def serialize(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "best_params": self.best_params,
            "best_value": self.best_value,
            "metric": self.metric,
            "n_combinations": self.n_combinations,
            "all_results": self.all_results[:50],  # cap at 50 for large grids
        }


def expand_grid(param_space: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """
    Expand a parameter space dict into a flat list of all combinations.

    param_space: {"fast": [10, 20], "slow": [40, 50]} →
        [{"fast": 10, "slow": 40}, {"fast": 10, "slow": 50}, ...]
    """
    if not param_space:
        return [{}]
    keys = list(param_space.keys())
    combos = list(product(*param_space.values()))
    return [dict(zip(keys, combo)) for combo in combos]


class GridSearchOptimizer:
    """
    Exhaustive grid search optimizer.

    Parameters
    ----------
    strategy_class : type
        Strategy class to instantiate with trial parameters.
    param_space : dict
        Mapping of param name → list of values to evaluate.
        Example: {"fast": [10, 20, 30], "slow": [40, 50, 60]}
    engine_cls : type
        VectorizedEngine or EventDrivenEngine class (not instance).
    metric : str
        Attribute on BacktestResult to optimise (e.g. "sharpe_ratio").
    maximize : bool
        True (default) = maximise metric; False = minimise.
    engine_kwargs : dict
        Extra kwargs forwarded to engine constructor.
    """

    def __init__(
        self,
        strategy_class: type,
        param_space: dict[str, list[Any]],
        engine_cls: type,
        metric: str = "sharpe_ratio",
        maximize: bool = True,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not param_space:
            raise ValueError("param_space must not be empty")
        for key, values in param_space.items():
            if not isinstance(values, list) or len(values) == 0:
                raise ValueError(f"param_space[{key!r}] must be a non-empty list")

        self.strategy_class = strategy_class
        self.param_space = param_space
        self.engine_cls = engine_cls
        self.metric = metric
        self.maximize = maximize
        self.engine_kwargs = engine_kwargs or {}
        self._result: GridSearchResult | None = None

    @property
    def results(self) -> GridSearchResult | None:
        """Return the result of the last run() call, or None if not yet run."""
        return self._result

    def run(
        self,
        data: pd.DataFrame,
        symbol: str = "UNKNOWN",
        timeframe: str = "1d",
    ) -> GridSearchResult:
        """
        Evaluate all parameter combinations on ``data``.

        Returns GridSearchResult with all_results ranked best → worst.
        """
        combos = expand_grid(self.param_space)
        evaluated: list[dict[str, Any]] = []

        for params in combos:
            try:
                strategy = self.strategy_class(**params)
                engine = self.engine_cls(**self.engine_kwargs)
                result: BacktestResult = engine.run(
                    data, strategy, symbol=symbol, timeframe=timeframe
                )
                result.compute_metrics()
                val = float(getattr(result, self.metric, float("-inf")))
                if val != val:  # NaN check
                    val = float("-inf") if self.maximize else float("inf")
                evaluated.append({"params": params, "value": val})
            except Exception:  # noqa: BLE001
                evaluated.append({"params": params, "value": float("-inf")})

        if not evaluated:
            raise RuntimeError("No parameter combinations could be evaluated")

        # Sort: best first
        evaluated.sort(key=lambda x: x["value"], reverse=self.maximize)

        best = evaluated[0]
        self._result = GridSearchResult(
            best_params=best["params"],
            best_value=best["value"],
            metric=self.metric,
            n_combinations=len(combos),
            all_results=evaluated,
        )
        return self._result
