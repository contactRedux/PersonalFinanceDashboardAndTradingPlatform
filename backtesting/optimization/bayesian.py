"""
Bayesian Optimizer using Optuna (TPE sampler).

Much more sample-efficient than exhaustive grid search for strategies with
three or more parameters.  Typically achieves equivalent or better results
in 10–100× fewer trials.

Example::

    from backtesting.optimization.bayesian import BayesianOptimizer
    from backtesting.strategies.sma_cross import SmaCrossStrategy
    from backtesting.engine.vectorized import VectorizedEngine

    opt = BayesianOptimizer(
        strategy_class=SmaCrossStrategy,
        param_space={"fast": (5, 50, 1), "slow": (20, 200, 5)},
        engine_cls=VectorizedEngine,
        metric="sharpe_ratio",
        n_trials=50,
    )
    result = opt.run(data, symbol="AAPL")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import optuna
import pandas as pd

from backtesting.engine.base import BacktestResult

# Silence Optuna's verbose progress output by default
optuna.logging.set_verbosity(logging.WARNING)


@dataclass
class BayesianResult:
    """Results from a Bayesian optimisation run."""

    best_params: dict[str, Any]
    best_value: float
    n_trials: int
    metric: str
    trials: list[dict[str, Any]] = field(default_factory=list)


class BayesianOptimizer:
    """
    Bayesian (TPE) optimizer wrapping Optuna.

    Parameters
    ----------
    strategy_class : type
        Strategy class to instantiate with trial parameters.
    param_space : dict
        Mapping of param name → (low, high, step) tuples.
        All parameters are treated as integers when step >= 1,
        otherwise floats.
    engine_cls : type
        VectorizedEngine or EventDrivenEngine (not instance).
    metric : str
        Attribute on BacktestResult to optimise (e.g. "sharpe_ratio").
    n_trials : int
        Number of Optuna trials to run.
    maximize : bool
        True (default) = maximise metric; False = minimise.
    engine_kwargs : dict
        Extra kwargs forwarded to engine constructor.
    """

    def __init__(
        self,
        strategy_class: type,
        param_space: dict[str, tuple[float, float, float]],
        engine_cls: type,
        metric: str = "sharpe_ratio",
        n_trials: int = 50,
        maximize: bool = True,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.strategy_class = strategy_class
        self.param_space = param_space
        self.engine_cls = engine_cls
        self.metric = metric
        self.n_trials = n_trials
        self.maximize = maximize
        self.engine_kwargs = engine_kwargs or {}

    def run(
        self,
        data: pd.DataFrame,
        symbol: str = "UNKNOWN",
        timeframe: str = "1d",
    ) -> BayesianResult:
        """
        Run the Bayesian optimisation.

        Parameters
        ----------
        data : pd.DataFrame
            OHLCV DataFrame with standard column names.
        symbol : str
            Ticker symbol (forwarded to engine.run).
        timeframe : str
            Bar timeframe string (forwarded to engine.run).

        Returns
        -------
        BayesianResult
        """

        def objective(trial: optuna.Trial) -> float:
            params: dict[str, Any] = {}
            for name, (low, high, step) in self.param_space.items():
                if float(step) >= 1.0:
                    params[name] = trial.suggest_int(name, int(low), int(high), step=int(step))
                else:
                    params[name] = trial.suggest_float(name, float(low), float(high), step=step)

            try:
                strategy = self.strategy_class(**params)
                engine = self.engine_cls(**self.engine_kwargs)
                result: BacktestResult = engine.run(data, strategy, symbol=symbol, timeframe=timeframe)
                result.compute_metrics()
                val = float(getattr(result, self.metric, float("-inf")))
                # Replace NaN / inf with a bad value so Optuna prunes gracefully
                if val != val or val == float("inf"):  # NaN check via reflexivity
                    val = float("-inf") if self.maximize else float("inf")
                return val
            except Exception:  # noqa: BLE001
                return float("-inf") if self.maximize else float("inf")

        direction = "maximize" if self.maximize else "minimize"
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction=direction, sampler=sampler)
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        all_trials = [
            {
                "number": t.number,
                "params": t.params,
                "value": t.value,
                "state": str(t.state),
            }
            for t in study.trials
        ]

        return BayesianResult(
            best_params=study.best_params,
            best_value=study.best_value,
            n_trials=len(study.trials),
            metric=self.metric,
            trials=all_trials,
        )
