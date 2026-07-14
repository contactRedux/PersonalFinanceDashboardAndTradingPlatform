"""
Shared data structures for the QuantNexus backtesting engines.

Both the vectorized and event-driven engines produce a ``BacktestResult``.
Strategies implement the ``Strategy`` protocol (duck-typed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd


# ─── Trade ────────────────────────────────────────────────────────────────────


@dataclass
class Trade:
    """A completed round-trip trade."""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    symbol: str
    direction: str  # "long" | "short"
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    mae: float = 0.0  # Maximum Adverse Excursion (worst intra-trade price)
    mfe: float = 0.0  # Maximum Favorable Excursion


# ─── BacktestResult ───────────────────────────────────────────────────────────


@dataclass
class BacktestResult:
    """Aggregated results from a backtest run."""

    symbol: str
    timeframe: str
    start: pd.Timestamp
    end: pd.Timestamp

    # Equity curve — one entry per bar
    equity_curve: list[float] = field(default_factory=list)
    timestamps: list[pd.Timestamp] = field(default_factory=list)

    # Trade log
    trades: list[Trade] = field(default_factory=list)

    # Summary metrics (computed by compute_metrics)
    initial_capital: float = 100_000.0
    final_equity: float = 0.0
    total_return_pct: float = 0.0
    cagr: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_duration_bars: float = 0.0
    exposure_pct: float = 0.0

    def compute_metrics(self) -> None:
        """Populate all summary metrics from equity_curve and trades."""
        if not self.equity_curve:
            return

        ec = np.array(self.equity_curve)
        self.final_equity = float(ec[-1])
        self.total_return_pct = (self.final_equity / self.initial_capital - 1.0) * 100.0

        # CAGR
        n_years = max((self.end - self.start).days / 365.25, 1 / 252)
        self.cagr = (self.final_equity / self.initial_capital) ** (1.0 / n_years) - 1.0

        # Drawdown
        peak = np.maximum.accumulate(ec)
        dd = (ec - peak) / np.where(peak > 0, peak, 1.0)
        self.max_drawdown_pct = float(np.min(dd)) * 100.0  # negative

        # Drawdown duration (longest contiguous underwater period)
        underwater = dd < 0
        if underwater.any():
            max_dur = 0
            cur_dur = 0
            for u in underwater:
                if u:
                    cur_dur += 1
                    max_dur = max(max_dur, cur_dur)
                else:
                    cur_dur = 0
            self.max_drawdown_duration = max_dur

        # Return series
        returns = np.diff(ec) / np.where(ec[:-1] > 0, ec[:-1], 1.0)
        if len(returns) > 1:
            mean_r = float(np.mean(returns)) * 252
            std_r = float(np.std(returns, ddof=1)) * np.sqrt(252)
            self.sharpe_ratio = (mean_r - 0.05) / std_r if std_r > 0 else 0.0
            downside = returns[returns < 0]
            ds_std = float(np.std(downside, ddof=1)) * np.sqrt(252) if len(downside) > 1 else 0.0
            self.sortino_ratio = (mean_r - 0.05) / ds_std if ds_std > 0 else 0.0
            self.calmar_ratio = (
                self.cagr / abs(self.max_drawdown_pct / 100.0)
                if self.max_drawdown_pct != 0
                else 0.0
            )

        # Trade stats
        self.total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        self.winning_trades = len(wins)
        self.losing_trades = len(losses)
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades else 0.0
        self.avg_win = float(np.mean([t.pnl for t in wins])) if wins else 0.0
        self.avg_loss = float(np.mean([t.pnl for t in losses])) if losses else 0.0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        if self.trades:
            durations = [
                (t.exit_time - t.entry_time).total_seconds()
                for t in self.trades
                if t.exit_time > t.entry_time
            ]
            self.avg_trade_duration_bars = float(np.mean(durations)) if durations else 0.0


# ─── Strategy Protocol ────────────────────────────────────────────────────────


class Strategy(Protocol):
    """
    Duck-typed protocol for all backtest strategies.

    ``generate_signals`` receives a DataFrame with OHLCV columns and must
    return a Series of integer signals aligned to the same index:
        +1  = enter long
        -1  = enter short (or exit long)
         0  = flat / hold
    """

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        ...
