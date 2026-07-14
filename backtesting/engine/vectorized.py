"""
Vectorized backtesting engine.

Applies signals to the entire price history in one NumPy pass.
Very fast for simple signal-based strategies (no partial fills,
no look-ahead prevention beyond the signal generation).

Usage::

    import pandas as pd
    from backtesting.engine.vectorized import VectorizedEngine
    from backtesting.strategies.sma_cross import SmaCrossStrategy

    data = pd.read_csv("AAPL.csv", index_col=0, parse_dates=True)
    engine = VectorizedEngine(initial_capital=100_000, commission=0.001)
    result = engine.run(data, SmaCrossStrategy(fast=20, slow=50), symbol="AAPL")
    result.compute_metrics()
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.base import BacktestResult, Trade


class VectorizedEngine:
    """
    Vectorized (whole-history) backtesting engine.

    Parameters
    ----------
    initial_capital : float
        Starting capital in USD.
    commission : float
        One-way commission as a fraction of trade value (e.g. 0.001 = 0.1%).
    slippage : float
        One-way slippage as a fraction of price (e.g. 0.0005 = 0.05%).
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(
        self,
        data: pd.DataFrame,
        strategy: object,
        symbol: str = "UNKNOWN",
        timeframe: str = "1d",
    ) -> BacktestResult:
        """
        Run a backtest over ``data`` using ``strategy``.

        ``data`` must have columns: open, high, low, close, volume.
        """
        data = data.copy()
        for col in ("open", "high", "low", "close", "volume"):
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        signals: pd.Series = strategy.generate_signals(data)  # type: ignore[attr-defined]
        signals = signals.fillna(0).astype(int)

        close = data["close"].to_numpy(dtype=float)
        timestamps = list(data.index)

        equity = np.full(len(close), self.initial_capital, dtype=float)
        position = 0  # shares held (+ = long, - = short)
        cash = float(self.initial_capital)
        trades: list[Trade] = []

        entry_bar: int | None = None
        entry_price: float = 0.0
        entry_direction: str = "long"
        mae_extreme: float = 0.0  # worst adverse price during trade
        mfe_extreme: float = 0.0  # best favorable price during trade

        for i in range(1, len(close)):
            sig = int(signals.iloc[i - 1])  # signal is known at bar close i-1 → act on open[i]
            price = close[i]

            # Update MAE/MFE if in a trade
            if position != 0 and entry_bar is not None:
                if entry_direction == "long":
                    mae_extreme = min(mae_extreme, data["low"].iloc[i])
                    mfe_extreme = max(mfe_extreme, data["high"].iloc[i])
                else:
                    mae_extreme = max(mae_extreme, data["high"].iloc[i])
                    mfe_extreme = min(mfe_extreme, data["low"].iloc[i])

            # Close existing position if direction changes or signal is 0
            if position != 0 and sig != (1 if position > 0 else -1):
                fill_price = price * (1 - self.slippage if position > 0 else 1 + self.slippage)
                pnl = (fill_price - entry_price) * position
                trade_value = abs(position) * fill_price
                pnl -= trade_value * self.commission  # exit commission
                cash += position * fill_price + pnl - abs(position) * fill_price * self.commission

                # Recompute cash properly
                cash = equity[i - 1] - abs(position) * entry_price
                cash += abs(position) * fill_price
                pnl_actual = (fill_price - entry_price) * abs(position) * (
                    1 if entry_direction == "long" else -1
                )
                cost = (abs(position) * entry_price + abs(position) * fill_price) * self.commission
                cash = equity[i - 1] + pnl_actual - cost

                mae = abs(mae_extreme - entry_price)
                mfe = abs(mfe_extreme - entry_price)
                trades.append(
                    Trade(
                        entry_time=timestamps[entry_bar],
                        exit_time=timestamps[i],
                        symbol=symbol,
                        direction=entry_direction,
                        entry_price=entry_price,
                        exit_price=fill_price,
                        quantity=abs(position),
                        pnl=pnl_actual - cost,
                        pnl_pct=(fill_price / entry_price - 1.0) * (
                            1 if entry_direction == "long" else -1
                        )
                        * 100.0,
                        mae=mae,
                        mfe=mfe,
                    )
                )
                position = 0
                entry_bar = None

            # Open new position
            if sig != 0 and position == 0:
                direction = "long" if sig > 0 else "short"
                fill_price = price * (1 + self.slippage if sig > 0 else 1 - self.slippage)
                position_value = cash * 0.95  # use 95% of available cash
                shares = position_value / fill_price if fill_price > 0 else 0.0
                cost = shares * fill_price * self.commission
                position = shares if sig > 0 else -shares
                cash = cash - position_value - cost
                entry_price = fill_price
                entry_bar = i
                entry_direction = direction
                mae_extreme = fill_price
                mfe_extreme = fill_price

            # Mark-to-market equity
            equity[i] = cash + abs(position) * close[i] if position != 0 else cash

        result = BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            start=pd.Timestamp(timestamps[0]),
            end=pd.Timestamp(timestamps[-1]),
            equity_curve=equity.tolist(),
            timestamps=list(timestamps),
            trades=trades,
            initial_capital=self.initial_capital,
        )
        return result
