"""
Event-driven backtesting engine.

Simulates trading bar-by-bar, preventing look-ahead bias by strict
separation of signal generation (uses data UP TO bar i) from fill
execution (uses OPEN of bar i+1).

Events processed per bar:
  1. MarketEvent  — new bar data available
  2. SignalEvent  — strategy emits a signal
  3. OrderEvent   — portfolio converts signal to order
  4. FillEvent    — broker simulates fill at next bar's open

Usage::

    from backtesting.engine.event_driven import EventDrivenEngine
    from backtesting.strategies.sma_cross import SmaCrossStrategy

    engine = EventDrivenEngine(initial_capital=100_000, commission=0.001)
    result = engine.run(data, SmaCrossStrategy(fast=20, slow=50), symbol="AAPL")
    result.compute_metrics()
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

import pandas as pd

from backtesting.engine.base import BacktestResult, Trade


# ─── Event types ──────────────────────────────────────────────────────────────


@dataclass
class MarketEvent:
    bar_index: int
    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SignalEvent:
    bar_index: int
    timestamp: pd.Timestamp
    signal: int  # +1 long, -1 short, 0 flat


@dataclass
class OrderEvent:
    bar_index: int
    direction: str  # "buy" | "sell"
    quantity: float


@dataclass
class FillEvent:
    bar_index: int
    timestamp: pd.Timestamp
    direction: str
    quantity: float
    fill_price: float
    commission: float


# ─── Portfolio ─────────────────────────────────────────────────────────────────


@dataclass
class _PortfolioState:
    cash: float
    position: float = 0.0  # +shares (long) or -shares (short)
    entry_price: float = 0.0
    entry_time: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    entry_direction: str = "long"
    mae: float = 0.0
    mfe: float = 0.0
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    timestamps: list[pd.Timestamp] = field(default_factory=list)


# ─── Engine ───────────────────────────────────────────────────────────────────


class EventDrivenEngine:
    """
    Event-driven backtesting engine.

    Parameters
    ----------
    initial_capital : float
        Starting capital in USD.
    commission : float
        Round-trip commission fraction per trade.
    slippage : float
        One-way slippage fraction applied to fill prices.
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
        Run bar-by-bar simulation.

        Signal for bar i is generated from data[0:i+1] (no look-ahead).
        Fill is executed at open of bar i+1.
        """
        data = data.copy().reset_index(drop=False)
        for col in ("open", "high", "low", "close", "volume"):
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        queue: Deque[
            MarketEvent | SignalEvent | OrderEvent | FillEvent
        ] = deque()
        portfolio = _PortfolioState(cash=self.initial_capital)

        n = len(data)

        for i in range(n):
            row = data.iloc[i]
            ts = pd.Timestamp(row.get("index", row.name))

            # 1. MarketEvent
            market_evt = MarketEvent(
                bar_index=i,
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            queue.append(market_evt)

            # Update MAE/MFE
            if portfolio.position != 0:
                if portfolio.entry_direction == "long":
                    portfolio.mae = min(portfolio.mae, market_evt.low)
                    portfolio.mfe = max(portfolio.mfe, market_evt.high)
                else:
                    portfolio.mae = max(portfolio.mae, market_evt.high)
                    portfolio.mfe = min(portfolio.mfe, market_evt.low)

            # 2. Generate signal from data up to and including bar i
            window = data.iloc[: i + 1].copy()
            if "index" in window.columns:
                window = window.set_index("index")
            signals: pd.Series = strategy.generate_signals(window)  # type: ignore[attr-defined]
            current_signal = int(signals.iloc[-1]) if len(signals) > 0 else 0
            queue.append(
                SignalEvent(bar_index=i, timestamp=ts, signal=current_signal)
            )

            # 3. Process events
            while queue:
                evt = queue.popleft()

                if isinstance(evt, SignalEvent):
                    desired = evt.signal
                    current_dir = 1 if portfolio.position > 0 else (-1 if portfolio.position < 0 else 0)
                    if desired != current_dir:
                        # Close existing position
                        if portfolio.position != 0:
                            queue.append(
                                OrderEvent(
                                    bar_index=i,
                                    direction="sell" if portfolio.position > 0 else "buy",
                                    quantity=abs(portfolio.position),
                                )
                            )
                        # Open new position
                        if desired != 0 and i + 1 < n:
                            next_open = float(data.iloc[i + 1]["open"])
                            fill_price = next_open * (
                                1 + self.slippage if desired > 0 else 1 - self.slippage
                            )
                            position_value = portfolio.cash * 0.95
                            qty = position_value / fill_price if fill_price > 0 else 0.0
                            comm = qty * fill_price * self.commission
                            queue.append(
                                FillEvent(
                                    bar_index=i + 1,
                                    timestamp=pd.Timestamp(data.iloc[i + 1].get("index", data.index[i + 1])),
                                    direction="buy" if desired > 0 else "sell",
                                    quantity=qty,
                                    fill_price=fill_price,
                                    commission=comm,
                                )
                            )

                elif isinstance(evt, OrderEvent):
                    # Close position at next bar open
                    if portfolio.position != 0 and i + 1 < n:
                        next_open = float(data.iloc[i + 1]["open"])
                        fill_price = next_open * (
                            1 - self.slippage if portfolio.position > 0 else 1 + self.slippage
                        )
                        comm = abs(portfolio.position) * fill_price * self.commission
                        queue.append(
                            FillEvent(
                                bar_index=i + 1,
                                timestamp=pd.Timestamp(data.iloc[i + 1].get("index", data.index[i + 1])),
                                direction="sell" if portfolio.position > 0 else "buy",
                                quantity=abs(portfolio.position),
                                fill_price=fill_price,
                                commission=comm,
                            )
                        )

                elif isinstance(evt, FillEvent):
                    if evt.direction == "buy":
                        cost = evt.quantity * evt.fill_price + evt.commission
                        portfolio.cash -= cost
                        portfolio.position += evt.quantity
                        portfolio.entry_price = evt.fill_price
                        portfolio.entry_time = evt.timestamp
                        portfolio.entry_direction = "long"
                        portfolio.mae = evt.fill_price
                        portfolio.mfe = evt.fill_price
                    else:
                        qty = min(abs(portfolio.position), evt.quantity)
                        pnl = (evt.fill_price - portfolio.entry_price) * qty * (
                            1 if portfolio.entry_direction == "long" else -1
                        )
                        portfolio.cash += qty * evt.fill_price - evt.commission
                        portfolio.trades.append(
                            Trade(
                                entry_time=portfolio.entry_time,
                                exit_time=evt.timestamp,
                                symbol=symbol,
                                direction=portfolio.entry_direction,
                                entry_price=portfolio.entry_price,
                                exit_price=evt.fill_price,
                                quantity=qty,
                                pnl=pnl - evt.commission,
                                pnl_pct=(evt.fill_price / portfolio.entry_price - 1.0)
                                * (1 if portfolio.entry_direction == "long" else -1)
                                * 100.0,
                                mae=abs(portfolio.mae - portfolio.entry_price),
                                mfe=abs(portfolio.mfe - portfolio.entry_price),
                            )
                        )
                        portfolio.position -= qty if portfolio.position > 0 else -qty

            # Mark-to-market
            current_price = float(data.iloc[i]["close"])
            mtm = portfolio.cash + abs(portfolio.position) * current_price if portfolio.position != 0 else portfolio.cash
            portfolio.equity_curve.append(mtm)
            portfolio.timestamps.append(ts)

        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            start=pd.Timestamp(portfolio.timestamps[0]) if portfolio.timestamps else pd.Timestamp.now(),
            end=pd.Timestamp(portfolio.timestamps[-1]) if portfolio.timestamps else pd.Timestamp.now(),
            equity_curve=portfolio.equity_curve,
            timestamps=portfolio.timestamps,
            trades=portfolio.trades,
            initial_capital=self.initial_capital,
        )
