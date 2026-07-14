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

import asyncio
import logging

import pandas as pd

from backtesting.engine.base import BacktestResult, Trade

logger = logging.getLogger(__name__)


async def _load_ticks_from_db(
    symbol: str,
    start: str,
    end: str,
    dsn: str | None = None,
) -> pd.DataFrame:
    """
    Load tick data from PostgreSQL using asyncpg (direct, no SQLAlchemy).

    Parameters
    ----------
    symbol : str
        Ticker symbol (uppercased).
    start : str
        ISO8601 start datetime string.
    end : str
        ISO8601 end datetime string.
    dsn : str | None
        PostgreSQL DSN; falls back to DATABASE_URL env var.

    Returns
    -------
    pd.DataFrame with columns: timestamp, price, size, side
    """
    import os  # noqa: PLC0415

    try:
        import asyncpg  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("asyncpg is required for data_source='db'") from exc

    db_url = dsn or os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set; cannot load ticks from DB")

    # asyncpg uses postgres:// scheme
    pg_dsn = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )

    conn = await asyncpg.connect(pg_dsn)
    try:
        rows = await conn.fetch(
            "SELECT time, price, size, side FROM ticks"
            " WHERE symbol = $1 AND time BETWEEN $2 AND $3"
            " ORDER BY time ASC",
            symbol,
            start,
            end,
        )
    finally:
        await conn.close()

    if not rows:
        return pd.DataFrame(columns=["timestamp", "price", "size", "side"])

    return pd.DataFrame(
        {
            "timestamp": [r["time"] for r in rows],
            "price": [float(r["price"]) for r in rows],
            "size": [float(r["size"]) for r in rows],
            "side": [r["side"] for r in rows],
        }
    )


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
    data_source : str
        ``"file"`` (default) — ticks passed directly to :meth:`run`.
        ``"db"``             — load ticks from PostgreSQL via asyncpg.
    """

    def __init__(
        self,
        speed_multiplier: float = 1.0,
        initial_capital: float = 100_000.0,
        commission: float = 0.001,
        data_source: str = "file",
    ) -> None:
        self.speed_multiplier = speed_multiplier
        self.initial_capital = initial_capital
        self.commission = commission
        self.data_source = data_source

    def run(
        self,
        ticks: pd.DataFrame,
        strategy: object,
        symbol: str = "UNKNOWN",
        start: str | None = None,
        end: str | None = None,
    ) -> BacktestResult:
        """
        Replay ``ticks`` through ``strategy`` and return a ``BacktestResult``.

        When ``data_source="db"``, ``symbol``, ``start``, and ``end`` are used
        to load ticks from PostgreSQL (asyncpg). Falls back to the supplied
        ``ticks`` DataFrame on any DB error.

        ``ticks`` must have columns: timestamp, price, size.
        ``strategy`` must implement ``on_tick(price, size) -> int``
        where the return value is +1 (buy), -1 (sell/short), or 0 (hold).
        Falls back to ``generate_signals`` on a single-column DataFrame if
        ``on_tick`` is not available.
        """
        if self.data_source == "db" and start and end:
            try:
                loop = asyncio.new_event_loop()
                try:
                    db_ticks = loop.run_until_complete(
                        _load_ticks_from_db(symbol.upper(), start, end)
                    )
                finally:
                    loop.close()
                if not db_ticks.empty:
                    ticks = db_ticks
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "tick_replay: DB load failed, falling back to file data: %s", exc
                )

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
