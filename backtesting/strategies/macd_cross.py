"""
MACD Cross strategy.

Generates a long signal when the MACD line crosses above the signal line,
exits (flat) on a cross below. Optionally goes short on negative crosses.

Parameters
----------
fast : int
    Fast EMA period (default 12).
slow : int
    Slow EMA period (default 26).
signal : int
    Signal line period (default 9).
allow_short : bool
    If True, go short when MACD crosses below signal. Default False.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class MACDCrossStrategy:
    """MACD crossover strategy — compatible with both engine types."""

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        allow_short: bool = False,
    ) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        if signal < 1:
            raise ValueError(f"signal period must be >= 1, got {signal}")
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.allow_short = allow_short

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Return a Series of signals aligned to data.index:
            +1 = enter long  (MACD crossed above signal)
            -1 = short       (MACD crossed below signal, only when allow_short=True)
             0 = flat
        """
        close = data["close"]
        k = lambda n: 2 / (n + 1)  # noqa: E731

        # EMA via pandas ewm (same as TA-Lib)
        ema_fast = close.ewm(alpha=k(self.fast), min_periods=self.fast, adjust=False).mean()
        ema_slow = close.ewm(alpha=k(self.slow), min_periods=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(  # noqa: E501
            alpha=k(self.signal), min_periods=self.signal, adjust=False
        ).mean()

        # Detect crosses
        above = (macd_line > signal_line).astype(int)
        cross_up = (above.diff() > 0)
        cross_down = (above.diff() < 0)

        position = pd.Series(0, index=data.index)

        # Carry the last cross signal forward (hold until opposite cross)
        sig = np.zeros(len(data), dtype=int)
        current = 0
        for i in range(len(data)):
            if cross_up.iloc[i]:
                current = 1
            elif cross_down.iloc[i]:
                current = -1 if self.allow_short else 0
            sig[i] = current

        position[:] = sig
        return position
