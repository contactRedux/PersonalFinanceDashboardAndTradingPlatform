"""
OHLCV dataset builder for LSTM training.

Constructs sliding-window sequences from OHLCV + technical indicator features.
Labels are assigned based on the next-bar forward return:
  - 0: down  (return < -1%)
  - 1: flat  (-1% ≤ return ≤ +1%)
  - 2: up    (return > +1%)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import torch
    from torch.utils.data import Dataset

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


_THRESHOLD = 0.01  # 1% threshold for up/down classification


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute technical indicator features from an OHLCV DataFrame.

    Input columns required: open, high, low, close, volume
    Output: DataFrame with additional feature columns (NaN rows dropped).
    """
    out = df.copy()
    close = out["close"]
    volume = out["volume"]

    # Simple Moving Averages
    out["sma_10"] = close.rolling(10).mean()
    out["sma_20"] = close.rolling(20).mean()
    out["sma_50"] = close.rolling(50).mean()

    # RSI (14-period)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["rsi_14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    out["bb_upper"] = sma20 + 2 * std20
    out["bb_lower"] = sma20 - 2 * std20
    out["bb_position"] = (close - out["bb_lower"]) / (out["bb_upper"] - out["bb_lower"] + 1e-9)

    # Volume ratio
    out["volume_ratio"] = volume / volume.rolling(20).mean()

    # Returns
    out["return_1"] = close.pct_change(1)
    out["return_5"] = close.pct_change(5)
    out["return_10"] = close.pct_change(10)

    # Normalise price columns relative to current price
    out["high_rel"] = (out["high"] - close) / close
    out["low_rel"] = (out["low"] - close) / close
    out["open_rel"] = (out["open"] - close) / close

    return out.dropna()


def label_returns(df: pd.DataFrame, threshold: float = _THRESHOLD) -> pd.Series:
    """
    Create next-bar classification labels from forward returns.

    Returns a Series aligned with df.index.
    """
    fwd_return = df["close"].shift(-1) / df["close"] - 1
    labels = pd.cut(
        fwd_return,
        bins=[-float("inf"), -threshold, threshold, float("inf")],
        labels=[0, 1, 2],
    ).astype(float)
    return labels


_FEATURE_COLS = [
    "open_rel", "high_rel", "low_rel",
    "return_1", "return_5", "return_10",
    "sma_10", "sma_20", "sma_50",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_position",
    "volume_ratio",
]


if _TORCH_AVAILABLE:
    import torch
    from torch.utils.data import Dataset

    class OHLCVDataset(Dataset):
        """
        Sliding-window OHLCV dataset for LSTM training.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame (columns: open, high, low, close, volume).
        seq_len : int
            Length of each input sequence window (default 30 bars).
        threshold : float
            Return threshold for up/down classification (default 1%).
        """

        def __init__(
            self,
            df: pd.DataFrame,
            seq_len: int = 30,
            threshold: float = _THRESHOLD,
        ) -> None:
            featured = build_features(df)
            labels = label_returns(featured, threshold=threshold)

            # Drop last row (no forward return available)
            featured = featured.iloc[:-1]
            labels = labels.iloc[:-1]

            # Keep only feature columns that exist
            cols = [c for c in _FEATURE_COLS if c in featured.columns]
            X = featured[cols].values.astype(np.float32)
            y = labels.values.astype(np.int64)

            # Normalise each feature column to zero mean, unit variance
            self._mean = X.mean(axis=0, keepdims=True)
            self._std = X.std(axis=0, keepdims=True) + 1e-8
            X = (X - self._mean) / self._std

            self.X = X
            self.y = y
            self.seq_len = seq_len
            self.n_features = X.shape[1]

            # Valid indices: seq_len-1 ... len-1
            self._valid_start = seq_len - 1

        def __len__(self) -> int:
            return max(0, len(self.X) - self.seq_len + 1)

        def __getitem__(self, idx: int):
            start = idx
            end = idx + self.seq_len
            x_seq = torch.tensor(self.X[start:end], dtype=torch.float32)
            label = int(self.y[end - 1]) if not np.isnan(self.y[end - 1]) else 1
            return x_seq, label

else:
    class OHLCVDataset:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("PyTorch is required for OHLCVDataset")
