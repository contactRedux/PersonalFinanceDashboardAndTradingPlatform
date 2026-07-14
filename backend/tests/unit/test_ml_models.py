"""
Unit tests for ML models (LSTM, XGBoost) using synthetic data.

These tests do NOT require GPU or downloaded model weights.
They use small synthetic datasets to verify the training and inference pipelines.
"""

from __future__ import annotations

import sys
import os

import numpy as np
import pandas as pd
import pytest

# Ensure ml package is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    prices = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices + rng.uniform(0, 1, n),
            "low": prices - rng.uniform(0, 1, n),
            "close": prices + rng.normal(0, 0.2, n),
            "volume": rng.uniform(1_000_000, 5_000_000, n),
        },
        index=pd.date_range("2023-01-01", periods=n, freq="D"),
    )


# ─── LSTM tests (ST-16) ───────────────────────────────────────────────────────


@pytest.mark.skipif(
    not pytest.importorskip("torch", reason="torch not installed"),
    reason="torch not installed",
)
def test_lstm_dataset_builds_correctly():
    """OHLCVDataset builds sequences with correct shape."""
    torch = pytest.importorskip("torch")
    from ml.models.lstm.dataset import OHLCVDataset  # noqa: PLC0415

    df = _make_ohlcv(200)
    dataset = OHLCVDataset(df, seq_len=20)

    assert len(dataset) > 0
    x, y = dataset[0]
    assert x.shape[0] == 20  # seq_len
    assert x.shape[1] > 0   # n_features
    assert y in [0, 1, 2]   # 3 classes


@pytest.mark.skipif(
    not pytest.importorskip("torch", reason="torch not installed"),
    reason="torch not installed",
)
def test_lstm_model_forward_pass():
    """LSTMPricePredictor forward pass produces correct output shape."""
    torch = pytest.importorskip("torch")
    from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415

    model = LSTMPricePredictor(n_features=10, hidden_size=32)
    x = torch.randn(4, 20, 10)  # batch=4, seq_len=20, features=10
    out = model(x)
    assert out.shape == (4, 3)  # batch × 3 classes


@pytest.mark.skipif(
    not pytest.importorskip("torch", reason="torch not installed"),
    reason="torch not installed",
)
def test_lstm_predict_proba_sums_to_one():
    """predict_proba output probabilities sum to 1.0."""
    torch = pytest.importorskip("torch")
    from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415

    model = LSTMPricePredictor(n_features=10, hidden_size=32)
    x = torch.randn(1, 20, 10)
    probs = model.predict_proba(x)
    assert abs(float(probs.sum()) - 1.0) < 1e-5


@pytest.mark.skipif(
    not pytest.importorskip("torch", reason="torch not installed"),
    reason="torch not installed",
)
def test_lstm_training_runs_on_synthetic_data(tmp_path):
    """train_lstm completes without error on 1 year of synthetic data."""
    torch = pytest.importorskip("torch")
    import os  # noqa: PLC0415
    from unittest.mock import patch, MagicMock  # noqa: PLC0415

    # Patch yfinance to return synthetic data
    mock_yf = MagicMock()
    mock_yf.download.return_value = _make_ohlcv(252)

    with patch.dict(os.environ, {"ML_WEIGHTS_DIR": str(tmp_path)}):
        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            from ml.models.lstm import train as lstm_train_module  # noqa: PLC0415
            import importlib  # noqa: PLC0415
            importlib.reload(lstm_train_module)

            weight_path = lstm_train_module.train_lstm(
                ticker="SPY",
                start="2023-01-01",
                end="2024-01-01",
                epochs=2,  # fast for test
                hidden_size=32,
                seq_len=20,
                batch_size=16,
            )
    assert weight_path.exists()
    assert weight_path.suffix == ".pt"


# ─── XGBoost tests (ST-17) ────────────────────────────────────────────────────
# These tests run XGBoost in a subprocess to avoid a segfault caused by
# PyTorch's BLAS state conflicting with XGBoost's C extension when both are
# loaded in the same process (reproducible on macOS aarch64 with
# NumPy 2.5 + XGBoost 3.x + PyTorch 2.x).

import subprocess  # noqa: E402
from unittest.mock import patch  # noqa: E402, PLC0415

_XGB_SCRIPT = """\
import sys, os, json, tempfile
sys.path.insert(0, {repo_root!r})
sys.path.insert(0, os.path.join({repo_root!r}, "backend"))
# Set weights dir BEFORE importing the model (module-level _WEIGHTS_DIR reads env at import time)
os.environ["ML_WEIGHTS_DIR"] = sys.argv[1]
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 300
prices = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
df = pd.DataFrame(
    {{
        "open": prices,
        "high": prices + rng.uniform(0, 1, n),
        "low": prices - rng.uniform(0, 1, n),
        "close": prices + rng.normal(0, 0.2, n),
        "volume": rng.uniform(1_000_000, 5_000_000, n),
    }},
    index=pd.date_range("2023-01-01", periods=n, freq="D"),
)

from ml.models.xgboost.model import (
    XGBoostSignalClassifier,
    build_xgb_features,
    _LABEL_THRESHOLD,
)

featured = build_xgb_features(df)
featured["label"] = (featured["fwd_return_5"] > _LABEL_THRESHOLD).astype(int)
featured = featured.drop(columns=["fwd_return_5"], errors="ignore")

weights_dir = sys.argv[1]
# (Already set above; redundant but harmless)

clf = XGBoostSignalClassifier()
clf.train(featured, label_col="label")

result = clf.predict(featured)
assert result["signal"] in [0, 1], f"bad signal: {{result}}"
assert 0.0 <= result["probability"] <= 1.0, f"bad prob: {{result}}"

weight_path = clf.save("SPY")
assert os.path.exists(weight_path), f"weight file missing: {{weight_path}}"

loaded_clf = XGBoostSignalClassifier.load("SPY")
result2 = loaded_clf.predict(featured)
assert result2["signal"] in [0, 1], f"bad signal after load: {{result2}}"

# Feature importance
importance = clf.get_feature_importance()
assert len(importance) > 0, "empty feature importance"
assert all("feature" in i and "importance" in i for i in importance)
values = [i["importance"] for i in importance]
assert values == sorted(values, reverse=True), "importance not sorted"

print("OK")
"""

import os as _os
# tests/unit/test_ml_models.py → 4 levels up = workspace root
_REPO_ROOT = _os.path.dirname(
    _os.path.dirname(
        _os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__))
        )
    )
)
_PYTHON = sys.executable


def _run_xgb_script(tmp_path: "Path") -> subprocess.CompletedProcess:
    """Execute the XGBoost test script in an isolated subprocess."""
    script = _XGB_SCRIPT.format(repo_root=_REPO_ROOT)
    env = _os.environ.copy()
    env["PYTHONPATH"] = f"{_REPO_ROOT}{_os.pathsep}{_os.path.join(_REPO_ROOT, 'backend')}{_os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [_PYTHON, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


@pytest.mark.skipif(
    not pytest.importorskip("xgboost", reason="xgboost not installed"),
    reason="xgboost not installed",
)
def test_xgboost_train_and_predict(tmp_path):
    """XGBoost classifier trains and returns valid signal + probability (subprocess)."""
    result = _run_xgb_script(tmp_path)
    if result.returncode != 0:
        pytest.fail(
            f"XGBoost subprocess failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert "OK" in result.stdout


@pytest.mark.skipif(
    not pytest.importorskip("xgboost", reason="xgboost not installed"),
    reason="xgboost not installed",
)
def test_xgboost_feature_importance_non_empty(tmp_path):
    """get_feature_importance returns a non-empty ranked list (subprocess)."""
    # The subprocess test above already validates feature importance.
    # This test re-runs the same script and checks the exit code.
    result = _run_xgb_script(tmp_path)
    if result.returncode != 0:
        pytest.fail(
            f"XGBoost feature importance subprocess failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    assert "OK" in result.stdout
