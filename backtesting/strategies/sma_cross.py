"""
SMA Crossover strategy — classic demo strategy.

Generates a long signal when the fast SMA crosses above the slow SMA,
and exits (flat/short) when the fast SMA crosses below.

Parameters
----------
fast : int
    Fast SMA period (default 20).
slow : int
    Slow SMA period (default 50).
allow_short : bool
    If True, go short when fast < slow. Default False (long-only).
"""

from __future__ import annotations

import pandas as pd


class SmaCrossStrategy:
    """SMA crossover strategy — compatible with both engine types."""

    def __init__(self, fast: int = 20, slow: int = 50, allow_short: bool = False) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        self.fast = fast
        self.slow = slow
        self.allow_short = allow_short

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Return a Series of signals aligned to data.index:
            +1 = enter long
            -1 = short (only when allow_short=True)
             0 = flat
        """
        close = data["close"]
        fast_ma = close.rolling(self.fast, min_periods=self.fast).mean()
        slow_ma = close.rolling(self.slow, min_periods=self.slow).mean()

        signals = pd.Series(0, index=data.index)

        # Long when fast > slow
        signals[fast_ma > slow_ma] = 1

        if self.allow_short:
            # Short when fast < slow
            signals[fast_ma < slow_ma] = -1

        return signals
