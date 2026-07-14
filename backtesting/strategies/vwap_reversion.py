"""
VWAP Reversion strategy.

Buys when the close price is more than `threshold_pct` below the rolling VWAP,
exits when the close rises back above VWAP.

Note: VWAP requires volume data. The strategy degrades gracefully when
volume is unavailable (all zeros) — falls back to a rolling typical-price mean.

Parameters
----------
threshold_pct : float
    Percentage below VWAP at which to enter long (default 0.5 = 0.5%).
allow_short : bool
    If True, short when close is threshold_pct above VWAP. Default False.
"""

from __future__ import annotations

import pandas as pd


class VWAPReversionStrategy:
    """VWAP reversion strategy — compatible with both engine types."""

    def __init__(
        self,
        threshold_pct: float = 0.5,
        allow_short: bool = False,
    ) -> None:
        if threshold_pct <= 0:
            raise ValueError(f"threshold_pct must be > 0, got {threshold_pct}")
        self.threshold_pct = threshold_pct
        self.allow_short = allow_short

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Return a Series of signals aligned to data.index:
            +1 = enter long  (close < VWAP * (1 - threshold/100))
            -1 = short       (close > VWAP * (1 + threshold/100), allow_short only)
             0 = flat
        """
        close = data["close"]

        # Compute cumulative VWAP from the full data window
        if "volume" in data.columns and data["volume"].sum() > 0:
            high = data["high"] if "high" in data.columns else close
            low = data["low"] if "low" in data.columns else close
            typical_price = (high + low + close) / 3
            cum_tp_vol = (typical_price * data["volume"]).cumsum()
            cum_vol = data["volume"].cumsum()
            vwap = cum_tp_vol / cum_vol.replace(0, float("nan"))
        else:
            # No volume — use rolling mean of typical price as proxy
            high = data["high"] if "high" in data.columns else close
            low = data["low"] if "low" in data.columns else close
            typical_price = (high + low + close) / 3
            vwap = typical_price.expanding().mean()

        threshold = self.threshold_pct / 100.0
        signals = pd.Series(0, index=data.index)
        signals[close < vwap * (1 - threshold)] = 1
        if self.allow_short:
            signals[close > vwap * (1 + threshold)] = -1

        return signals
