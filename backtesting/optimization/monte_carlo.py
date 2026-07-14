"""
Monte Carlo simulator for backtesting results.

Bootstraps the trade P&L distribution to estimate the range of possible
equity curves, and computes confidence-interval metrics.

Usage::

    from backtesting.optimization.monte_carlo import MonteCarlo

    mc = MonteCarlo(n_simulations=1000, seed=42)
    mc_result = mc.run(backtest_result)
    print(mc_result.median_final_equity, mc_result.p05_max_drawdown)
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from backtesting.engine.base import BacktestResult


@dataclass
class MonteCarloResult:
    """Statistics from Monte Carlo simulation."""

    n_simulations: int
    # Final equity percentiles
    p05_final_equity: float
    p25_final_equity: float
    median_final_equity: float
    p75_final_equity: float
    p95_final_equity: float
    # Max drawdown percentiles (negative, %)
    p05_max_drawdown: float
    median_max_drawdown: float
    p95_max_drawdown: float
    # Sharpe percentiles
    p05_sharpe: float
    median_sharpe: float
    p95_sharpe: float
    # Probability of profit
    prob_profit: float
    # All simulated final equities (for histogram)
    all_final_equities: list[float]


class MonteCarlo:
    """
    Bootstrap Monte Carlo simulator.

    Re-samples individual trade P&Ls with replacement to generate
    alternative equity curve paths.

    Parameters
    ----------
    n_simulations : int
        Number of bootstrap runs.
    seed : int | None
        Random seed for reproducibility.
    """

    def __init__(self, n_simulations: int = 1000, seed: int | None = None) -> None:
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(seed)

    def run(self, result: BacktestResult) -> MonteCarloResult:
        """Run Monte Carlo simulation over ``result``'s trade PnL list."""
        if not result.trades:
            raise ValueError("BacktestResult has no trades — cannot run Monte Carlo.")

        pnls = np.array([t.pnl for t in result.trades])
        n_trades = len(pnls)
        initial = result.initial_capital

        final_equities: list[float] = []
        max_drawdowns: list[float] = []
        sharpes: list[float] = []

        for _ in range(self.n_simulations):
            # Bootstrap: sample with replacement
            sampled = self.rng.choice(pnls, size=n_trades, replace=True)
            equity = np.concatenate([[initial], initial + np.cumsum(sampled)])

            # Final equity
            final_equities.append(float(equity[-1]))

            # Max drawdown
            peak = np.maximum.accumulate(equity)
            dd = (equity - peak) / np.where(peak > 0, peak, 1.0)
            max_drawdowns.append(float(np.min(dd)) * 100.0)

            # Sharpe
            returns = np.diff(equity) / np.where(equity[:-1] > 0, equity[:-1], 1.0)
            if len(returns) > 1 and np.std(returns) > 0:
                sharpes.append(
                    float(np.mean(returns) * 252 - 0.05) / (float(np.std(returns)) * np.sqrt(252))
                )
            else:
                sharpes.append(0.0)

        fe = np.array(final_equities)
        dd_arr = np.array(max_drawdowns)
        sh_arr = np.array(sharpes)

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            p05_final_equity=float(np.percentile(fe, 5)),
            p25_final_equity=float(np.percentile(fe, 25)),
            median_final_equity=float(np.percentile(fe, 50)),
            p75_final_equity=float(np.percentile(fe, 75)),
            p95_final_equity=float(np.percentile(fe, 95)),
            p05_max_drawdown=float(np.percentile(dd_arr, 5)),
            median_max_drawdown=float(np.percentile(dd_arr, 50)),
            p95_max_drawdown=float(np.percentile(dd_arr, 95)),
            p05_sharpe=float(np.percentile(sh_arr, 5)),
            median_sharpe=float(np.percentile(sh_arr, 50)),
            p95_sharpe=float(np.percentile(sh_arr, 95)),
            prob_profit=float(np.mean(fe > initial)),
            all_final_equities=final_equities,
        )
