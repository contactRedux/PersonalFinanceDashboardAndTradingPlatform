"""
Risk metrics calculations.

Implements:
  - VaR (Value at Risk): Historical simulation, Parametric
  - CVaR (Conditional VaR / Expected Shortfall)
  - Sharpe Ratio
  - Sortino Ratio
  - Calmar Ratio
  - Beta / Alpha vs benchmark
  - Max Drawdown
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def max_drawdown(equity_curve: Sequence[float]) -> tuple[float, int]:
    """
    Compute maximum drawdown from an equity curve.
    Returns: (max_drawdown_pct, duration_in_periods)
    """
    if len(equity_curve) < 2:
        return 0.0, 0

    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_duration = 0
    current_dd_start = 0

    for i, v in enumerate(equity_curve):
        if v > peak:
            peak = v
            current_dd_start = i
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_duration = i - current_dd_start

    return round(max_dd, 6), max_dd_duration


def historical_var(returns: Sequence[float], confidence: float = 0.95) -> float:
    """
    Historical simulation VaR at given confidence level.
    Returns: VaR as a positive percentage (e.g., 0.05 = 5% loss).
    """
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    index = int((1 - confidence) * len(sorted_returns))
    return abs(sorted_returns[max(0, index)])


def cvar(returns: Sequence[float], confidence: float = 0.95) -> float:
    """
    Conditional VaR (Expected Shortfall) — average loss beyond VaR.
    """
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    cutoff = int((1 - confidence) * len(sorted_returns))
    tail = sorted_returns[: max(1, cutoff)]
    return abs(statistics.mean(tail)) if tail else 0.0


def sharpe_ratio(returns: Sequence[float], risk_free_rate: float = 0.05) -> float:
    """
    Sharpe Ratio: (mean return - risk-free rate) / std deviation.
    Assumes `returns` are daily returns; annualizes automatically.
    """
    if len(returns) < 2:
        return 0.0
    mean_r = statistics.mean(returns) * 252  # annualize
    std_r = statistics.stdev(returns) * math.sqrt(252)
    return (mean_r - risk_free_rate) / std_r if std_r > 0 else 0.0


def sortino_ratio(returns: Sequence[float], risk_free_rate: float = 0.05) -> float:
    """
    Sortino Ratio: (mean return - risk-free rate) / downside deviation.
    """
    if len(returns) < 2:
        return 0.0
    mean_r = statistics.mean(returns) * 252
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf")
    downside_std = statistics.stdev(downside) * math.sqrt(252)
    return (mean_r - risk_free_rate) / downside_std if downside_std > 0 else 0.0


def calmar_ratio(returns: Sequence[float], equity_curve: Sequence[float]) -> float:
    """
    Calmar Ratio: CAGR / Max Drawdown.
    """
    if not returns or not equity_curve:
        return 0.0
    cagr = statistics.mean(returns) * 252
    mdd, _ = max_drawdown(equity_curve)
    return cagr / mdd if mdd > 0 else 0.0


def beta_alpha(
    portfolio_returns: Sequence[float],
    benchmark_returns: Sequence[float],
    risk_free_rate: float = 0.05 / 252,
) -> tuple[float, float]:
    """
    Compute portfolio Beta and Alpha vs benchmark.
    Returns: (beta, alpha_annualized)
    """
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return 1.0, 0.0

    pr = portfolio_returns[:n]
    br = benchmark_returns[:n]

    cov_pr_br = sum(
        (pr[i] - statistics.mean(pr)) * (br[i] - statistics.mean(br)) for i in range(n)
    ) / (n - 1)
    var_br = statistics.variance(br)

    beta = cov_pr_br / var_br if var_br > 0 else 1.0
    excess_portfolio = statistics.mean(pr) - risk_free_rate
    excess_benchmark = statistics.mean(br) - risk_free_rate
    alpha = (excess_portfolio - beta * excess_benchmark) * 252

    return round(beta, 4), round(alpha, 6)


def position_size_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Kelly Criterion position size fraction.
    Returns: optimal fraction of capital to risk.
    """
    if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    kelly = (b * win_rate - q) / b
    # Use half-Kelly for safety
    return max(0.0, min(kelly * 0.5, 0.25))  # Cap at 25%
