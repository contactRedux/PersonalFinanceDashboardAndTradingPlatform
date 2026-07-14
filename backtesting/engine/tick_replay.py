"""
Tick-level replay engine for backtesting.

Processes a DataFrame of raw ticks in chronological order,
simulating market events at tick granularity.

Usage::

    import pandas as pd
    from backtesting.engine.tick_replay import TickReplayEngine

    ticks = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="1s"),
        "price": [...],
        "size": [...],
    })
    engine = TickReplayEngine(speed_multiplier=1.0)
    result = engine.run(ticks, strategy, symbol="AAPL")
    result.compute_metrics()
"""

from __future__ import annotations

import pandas as pd

from backtesting.engine.base import BacktestResult, Trade


class TickReplayEngine:
    """
    Tick-level backtesting engine.

    Parameters
    ----------
    speed_multiplier : float
        Replay speed multiplier (informational; does not affect results).
    initial_capital : float
        Starting capital in USD.
    commission : float
        One-way commission as a fraction of trade value.
    """

    def __init__(
        self,
        speed_multiplier: float = 1.0,
        initial_capital: float = 100_000.0,
        commission: float = 0.001,
    ) -> None:
        self.speed_multiplier = speed_multiplier
        self.initial_capital = initial_capital
        self.commission = commission

    def run(
        self,
        ticks: pd.DataFrame,
        strategy: object,
        symbol: str = "UNKNOWN",
    ) -> BacktestResult:
        """
        Replay ``ticks`` through ``strategy`` and return a ``BacktestResult``.

        ``ticks`` must have columns: timestamp, price, size.
        ``strategy`` must implement ``on_tick(price, size) -> int``
        where the return value is +1 (buy), -1 (sell/short), or 0 (hold).
        Falls back to ``generate_signals`` on a single-column DataFrame if
        ``on_tick`` is not available.
        """
        ticks = ticks.copy()
        for col in ("timestamp", "price", "size"):
            if col not in ticks.columns:
                raise ValueError(f"Missing required column: {col}")

        ticks = ticks.sort_values("timestamp").reset_index(drop=True)

        n = len(ticks)
        if n == 0:
            now = pd.Timestamp("now", tz="UTC")
            return BacktestResult(
                symbol=symbol,
                timeframe="tick",
                start=now,
                end=now,
                equity_curve=[self.initial_capital],
                timestamps=[now],
                trades=[],
                initial_capital=self.initial_capital,
            )

        prices = ticks["price"].to_numpy(dtype=float)
        sizes = ticks["size"].to_numpy(dtype=float)
        timestamps = list(ticks["timestamp"])

        # Resolve signal source
        has_on_tick = hasattr(strategy, "on_tick") and callable(
            getattr(strategy, "on_tick")
        )
        if not has_on_tick:
            # Fallback: treat ticks as OHLCV-like single-column price series
            price_df = pd.DataFrame({"close": prices}, index=ticks["timestamp"])
            for col in ("open", "high", "low", "volume"):
                price_df[col] = prices if col != "volume" else sizes
            raw_signals = strategy.generate_signals(price_df)  # type: ignore[attr-defined]
            raw_signals = raw_signals.fillna(0).astype(int)
            signal_list = list(raw_signals)
        else:
            signal_list = None

        equity_curve: list[float] = []
        cash = float(self.initial_capital)
        position = 0.0
        entry_price = 0.0
        entry_time: pd.Timestamp | None = None
        entry_direction = "long"
        trades: list[Trade] = []

        for i in range(n):
            price = prices[i]
            size = sizes[i]

            if has_on_tick:
                sig = int(strategy.on_tick(price, size))  # type: ignore[union-attr]
            else:
                sig = int(signal_list[i]) if signal_list is not None else 0  # type: ignore[index]

            # Close position if signal flips or goes flat
            if position != 0 and sig != (1 if position > 0 else -1):
                fill = price
                direction = "long" if position > 0 else "short"
                pnl_raw = (fill - entry_price) * abs(position) * (
                    1 if direction == "long" else -1
                )
                cost = (abs(position) * entry_price + abs(position) * fill) * self.commission
                pnl = pnl_raw - cost
                cash += abs(position) * fill - abs(position) * fill * self.commission
                trades.append(
                    Trade(
                        entry_time=entry_time or pd.Timestamp(timestamps[i]),
                        exit_time=pd.Timestamp(timestamps[i]),
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=fill,
                        quantity=abs(position),
                        pnl=pnl,
                        pnl_pct=(fill / entry_price - 1.0) * (
                            1 if direction == "long" else -1
                        )
                        * 100.0,
                    )
                )
                position = 0.0

            # Open new position
            if sig != 0 and position == 0:
                fill = price
                value = cash * 0.95
                shares = value / fill if fill > 0 else 0.0
                cost = shares * fill * self.commission
                position = shares if sig > 0 else -shares
                cash -= value + cost
                entry_price = fill
                entry_time = pd.Timestamp(timestamps[i])
                entry_direction = "long" if sig > 0 else "short"

            equity = cash + abs(position) * price if position != 0 else cash
            equity_curve.append(equity)

        return BacktestResult(
            symbol=symbol,
            timeframe="tick",
            start=pd.Timestamp(timestamps[0]),
            end=pd.Timestamp(timestamps[-1]),
            equity_curve=equity_curve,
            timestamps=list(timestamps),
            trades=trades,
            initial_capital=self.initial_capital,
        )
