"""
Training script for the RegimeDetector HMM.

Generates synthetic market feature data, fits the model, and saves it to
ml/models/hmm/regime_detector.pkl.

Usage:
    python ml/models/hmm/train.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_HERE = Path(__file__).parent
_MODEL_PATH = _HERE / "regime_detector.pkl"

_BARS = 200
_RNG_SEED = 42


def _generate_synthetic_features(n_bars: int = _BARS, seed: int = _RNG_SEED) -> np.ndarray:
    """
    Build a (n_bars, 3) feature matrix:
      col 0 — VIX proxy  : rolling 20-day return std × 100
      col 1 — yield-spread proxy : mock 10Y-2Y spread
      col 2 — momentum   : 20-day return
    """
    rng = np.random.default_rng(seed)
    # Simulate close prices with random walk
    log_returns = rng.normal(loc=0.0003, scale=0.012, size=n_bars + 20)
    closes = 100.0 * np.exp(np.cumsum(log_returns))

    volatility = np.array(
        [np.std(log_returns[max(0, i - 20) : i]) * 100 for i in range(20, n_bars + 20)]
    )
    momentum = np.array(
        [(closes[i] / closes[max(0, i - 20)] - 1) for i in range(20, n_bars + 20)]
    )
    # Mock yield-spread: mean-reverting process around 0.5
    spread = np.zeros(n_bars)
    spread[0] = 0.5
    for i in range(1, n_bars):
        spread[i] = 0.98 * spread[i - 1] + rng.normal(0, 0.05)

    return np.column_stack([volatility, spread, momentum])


def train(save_path: Path = _MODEL_PATH) -> None:
    from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

    features = _generate_synthetic_features()
    print(f"Feature matrix shape: {features.shape}")

    detector = RegimeDetector(n_components=4, n_iter=100, random_state=_RNG_SEED)
    detector.fit(features)
    print("Model fitted. Regime distribution on training data:")

    preds = detector.predict(features)
    for idx in range(4):
        count = int(np.sum(preds == idx))
        label = detector.regime_label(idx)
        print(f"  {label}: {count} bars ({count / len(preds) * 100:.1f}%)")

    detector.save(save_path)
    print(f"Model saved → {save_path}")


if __name__ == "__main__":
    train()
