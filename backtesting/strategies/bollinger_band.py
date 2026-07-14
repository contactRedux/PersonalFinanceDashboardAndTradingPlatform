"""
Bollinger Band mean-reversion strategy.

Buys when close touches or breaks below the lower Bollinger Band,
exits when close touches or breaks above the upper Bollinger Band.

Parameters
----------
period : int
    Moving average period for the bands (default 20).
std_dev : float
    Number of standard deviations for band width (default 2.0).
allow_short : bool
    If True, short when price breaks above upper band. Default False.
"""

from __future__ import annotations

import pandas as pd


class BollingerBandStrategy:
    """Bollinger Band mean-reversion strategy — compatible with both engine types."""

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        allow_short: bool = False,
    ) -> None:
        if period < 2:
            raise ValueError(f"period must be >= 2, got {period}")
        if std_dev <= 0:
            raise ValueError(f"std_dev must be > 0, got {std_dev}")
        self.period = period
        self.std_dev = std_dev
        self.allow_short = allow_short

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Return a Series of signals aligned to data.index:
            +1 = enter long  (close < lower band)
            -1 = short       (close > upper band, only when allow_short=True)
             0 = flat (close between bands)
        """
        close = data["close"]
        rolling = close.rolling(self.period, min_periods=self.period)
        mid = rolling.mean()
        std = rolling.std(ddof=1)

        upper = mid + self.std_dev * std
        lower = mid - self.std_dev * std

        signals = pd.Series(0, index=data.index)
        signals[close < lower] = 1
        if self.allow_short:
            signals[close > upper] = -1

        return signals
