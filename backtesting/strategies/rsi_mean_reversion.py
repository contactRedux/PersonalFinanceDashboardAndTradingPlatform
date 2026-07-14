"""
RSI Mean Reversion strategy.

Generates a long signal when RSI drops below oversold threshold,
exits (flat) when RSI rises above overbought threshold.

Parameters
----------
period : int
    RSI period (default 14).
oversold : float
    RSI level below which to buy (default 30).
overbought : float
    RSI level above which to exit / go short (default 70).
allow_short : bool
    If True, short when RSI > overbought. Default False (long-only).
"""

from __future__ import annotations

import pandas as pd


class RSIMeanReversionStrategy:
    """RSI mean-reversion strategy — compatible with both engine types."""

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        allow_short: bool = False,
    ) -> None:
        if period < 2:
            raise ValueError(f"period must be >= 2, got {period}")
        if not (0 < oversold < overbought < 100):
            raise ValueError("oversold must be 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.allow_short = allow_short

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Return a Series of signals aligned to data.index:
            +1 = enter long  (RSI < oversold)
            -1 = short       (RSI > overbought, only when allow_short=True)
             0 = flat
        """
        close = data["close"]

        # Compute RSI via Wilder's smoothing (identical to TA-Lib)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, float("inf"))
        rsi_series = 100 - (100 / (1 + rs))

        signals = pd.Series(0, index=data.index)
        signals[rsi_series < self.oversold] = 1
        if self.allow_short:
            signals[rsi_series > self.overbought] = -1

        return signals
