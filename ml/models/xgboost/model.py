"""
XGBoost signal classifier — binary long / no-position signal.

Architecture:
  - Features: OHLCV + technical indicators + lagged returns (1, 3, 5, 10 bars)
  - Output: binary signal (1=long, 0=no-position) + probability score
  - Weights saved to disk as JSON (xgboost native format)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import xgboost as xgb

    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

_WEIGHTS_DIR = Path(
    os.environ.get("ML_WEIGHTS_DIR", "/app/data/ml_weights/xgboost")
)

# Label threshold: forward 5-bar return > 1% = long signal
_LABEL_THRESHOLD = 0.01
_LABEL_HORIZON = 5


def build_xgb_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix from OHLCV + indicators + lagged returns.

    Same base indicators as the LSTM pipeline plus lagged returns.
    Returns DataFrame with NaN rows dropped.
    """
    from ml.models.lstm.dataset import build_features  # noqa: PLC0415

    featured = build_features(df)
    close = featured["close"]

    # Lagged returns
    for lag in [1, 3, 5, 10]:
        featured[f"lag_{lag}"] = close.pct_change(lag)

    # Forward 5-bar return (for labelling — not included as feature)
    featured["fwd_return_5"] = close.shift(-_LABEL_HORIZON) / close - 1

    return featured.dropna()


_FEATURE_COLS = [
    "open_rel", "high_rel", "low_rel",
    "return_1", "return_5", "return_10",
    "sma_10", "sma_20", "sma_50",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_position",
    "volume_ratio",
    "lag_1", "lag_3", "lag_5", "lag_10",
]


class XGBoostSignalClassifier:
    """
    Binary XGBoost classifier: long (1) vs no-position (0).

    Trained on features from ``build_xgb_features()``.
    """

    def __init__(self) -> None:
        if not _XGB_AVAILABLE:
            raise ImportError("xgboost is required. Install with: pip install xgboost>=2.1.0")
        self._model: "xgb.XGBClassifier | None" = None
        self._feature_cols: list[str] = []

    def train(self, df: pd.DataFrame, label_col: str = "label") -> None:
        """
        Train the classifier on a prepared feature DataFrame.

        The DataFrame must have feature columns + ``label_col``.
        """
        cols = [c for c in _FEATURE_COLS if c in df.columns]
        self._feature_cols = cols
        X = df[cols].to_numpy(dtype=np.float32)
        y = df[label_col].to_numpy(dtype=np.int32)

        self._model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            n_jobs=1,  # single-threaded: avoids segfault on macOS with NumPy 2.x
            tree_method="hist",
        )
        self._model.fit(X, y)

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Predict signal for the most recent row.

        Returns {"signal": 0|1, "probability": float}
        """
        if self._model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        cols = [c for c in self._feature_cols if c in df.columns]
        X = df[cols].iloc[[-1]].values
        signal = int(self._model.predict(X)[0])
        prob = float(self._model.predict_proba(X)[0][signal])
        return {"signal": signal, "probability": prob}

    def get_feature_importance(self) -> list[dict]:
        """
        Return feature importance ranked by gain (descending).

        Output: [{"feature": str, "importance": float}, ...]
        """
        if self._model is None:
            raise RuntimeError("Model not trained.")
        importance = self._model.get_booster().get_score(importance_type="gain")
        ranked = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        return [{"feature": k, "importance": round(v, 4)} for k, v in ranked]

    def save(self, ticker: str) -> Path:
        """Save model to disk in XGBoost JSON format."""
        if self._model is None:
            raise RuntimeError("Model not trained.")
        _WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        path = _WEIGHTS_DIR / f"{ticker.upper()}.json"
        self._model.save_model(str(path))
        # Also save feature list
        import json  # noqa: PLC0415

        meta_path = _WEIGHTS_DIR / f"{ticker.upper()}_meta.json"
        meta_path.write_text(json.dumps({"feature_cols": self._feature_cols}))
        return path

    @classmethod
    def load(cls, ticker: str) -> "XGBoostSignalClassifier":
        """Load a trained model from disk."""
        path = _WEIGHTS_DIR / f"{ticker.upper()}.json"
        meta_path = _WEIGHTS_DIR / f"{ticker.upper()}_meta.json"
        if not path.exists():
            raise FileNotFoundError(f"No trained model found for {ticker}")
        obj = cls()
        obj._model = xgb.XGBClassifier()
        obj._model.load_model(str(path))
        if meta_path.exists():
            import json  # noqa: PLC0415

            obj._feature_cols = json.loads(meta_path.read_text()).get("feature_cols", _FEATURE_COLS)
        else:
            obj._feature_cols = list(_FEATURE_COLS)
        return obj
