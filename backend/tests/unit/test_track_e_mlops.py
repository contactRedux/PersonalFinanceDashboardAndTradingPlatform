"""
Tests for Track E — MLOps pipeline.

E-1: MLflow ExperimentTracker
E-2: FeatureStore and compute_features
E-3: ModelRegistry
E-4: TFTModel architecture
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Ensure ml package is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────


def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame with n rows."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.1
    volume = np.abs(np.random.randn(n) * 1e6) + 1e5
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


# ────────────────────────────────────────────────────────────────────────────
# E-2 · Feature Store
# ────────────────────────────────────────────────────────────────────────────


class TestComputeFeatures:
    def test_returns_dict_of_floats(self):
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(200)
        features = compute_features(df)
        assert isinstance(features, dict)
        assert len(features) > 0
        for v in features.values():
            assert isinstance(v, float)

    def test_returns_empty_for_short_df(self):
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(10)
        assert compute_features(df) == {}

    def test_returns_empty_for_missing_columns(self):
        from ml.feature_store.store import compute_features

        df = pd.DataFrame({"price": [1.0, 2.0, 3.0] * 20})
        assert compute_features(df) == {}

    def test_all_expected_keys_present(self):
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(250)
        features = compute_features(df)
        expected_keys = {
            "return_1d", "return_5d", "return_20d", "rsi_14",
            "atr_14", "rolling_vol_20", "bb_width_20",
            "vwap_dev", "obv_change_5d", "vol_ratio_20",
            "sma_50_200_ratio", "ema_12_26_ratio",
        }
        assert expected_keys.issubset(set(features.keys()))

    def test_rsi_in_valid_range(self):
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(200)
        features = compute_features(df)
        assert 0 <= features["rsi_14"] <= 100

    def test_atr_is_positive(self):
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(200)
        features = compute_features(df)
        assert features["atr_14"] >= 0

    def test_case_insensitive_columns(self):
        """Feature computation should work with UPPER or mixed-case column names."""
        from ml.feature_store.store import compute_features

        df = _make_ohlcv(200)
        df.columns = [c.upper() for c in df.columns]
        features = compute_features(df)
        assert len(features) > 0


class TestFeatureStoreCache:
    @pytest.mark.asyncio
    async def test_l1_cache_hit_avoids_recompute(self):
        from ml.feature_store.store import FeatureStore

        df = _make_ohlcv(200)
        store = FeatureStore()

        # First call computes
        f1 = await store.get_or_compute("SPY", "1d", df, end_date="2024-01-01")
        # Second call must hit L1 (same object)
        f2 = await store.get_or_compute("SPY", "1d", df, end_date="2024-01-01")

        assert f1 == f2

    @pytest.mark.asyncio
    async def test_l2_redis_get_used_when_l1_miss(self):
        from ml.feature_store.store import FeatureStore

        df = _make_ohlcv(200)
        store = FeatureStore(redis_url="redis://fake:6379/99")

        # Inject a mock Redis that returns a cached value
        mock_redis = AsyncMock()
        expected = {"return_1d": 0.01, "rsi_14": 55.0}
        mock_redis.get = AsyncMock(return_value=json.dumps(expected))
        store._redis = mock_redis

        result = await store.get_or_compute("TSLA", "1d", df, end_date="2024-01-01")
        assert result == expected

    @pytest.mark.asyncio
    async def test_invalidate_removes_l1_entry(self):
        from ml.feature_store.store import FeatureStore

        df = _make_ohlcv(200)
        store = FeatureStore()
        await store.get_or_compute("NVDA", "1d", df, end_date="2024-01-01")
        store.invalidate("NVDA", "1d", "2024-01-01")

        # After invalidate, L1 should not contain the key
        from ml.feature_store.store import _cache_key
        key = _cache_key("NVDA", "1d", "2024-01-01")
        assert key not in store._l1


# ────────────────────────────────────────────────────────────────────────────
# E-1 · Experiment Tracker
# ────────────────────────────────────────────────────────────────────────────


class TestExperimentTrackerNoop:
    """When MLflow is not importable, all tracker calls are no-ops."""

    def test_log_params_no_crash_when_mlflow_missing(self):
        from ml.experiments.tracker import ExperimentTracker

        tracker = ExperimentTracker("test-exp")
        with patch("ml.experiments.tracker._get_mlflow", return_value=None):
            tracker.log_params({"lr": 0.001})  # must not raise

    def test_log_metrics_no_crash_when_mlflow_missing(self):
        from ml.experiments.tracker import ExperimentTracker

        tracker = ExperimentTracker("test-exp")
        with patch("ml.experiments.tracker._get_mlflow", return_value=None):
            tracker.log_metrics({"loss": 0.5}, step=1)  # must not raise

    def test_start_run_yields_none_when_mlflow_missing(self):
        from ml.experiments.tracker import ExperimentTracker

        tracker = ExperimentTracker("test-exp")
        with patch("ml.experiments.tracker._get_mlflow", return_value=None):
            with tracker.start_run() as run_id:
                assert run_id is None

    def test_get_best_run_returns_none_when_mlflow_missing(self):
        from ml.experiments.tracker import ExperimentTracker

        tracker = ExperimentTracker("test-exp")
        with patch("ml.experiments.tracker._get_mlflow", return_value=None):
            result = tracker.get_best_run("val_loss")
            assert result is None


class TestExperimentTrackerWithMlflow:
    """When MLflow IS available, verify correct calls are made."""

    def test_start_run_calls_mlflow_start_run(self):
        from ml.experiments.tracker import ExperimentTracker

        mock_mlflow = MagicMock()
        mock_run = MagicMock()
        mock_run.info.run_id = "abc123"
        mock_mlflow.start_run.return_value.__enter__ = lambda s: mock_run
        mock_mlflow.start_run.return_value = mock_run
        mock_mlflow.get_experiment_by_name.return_value = MagicMock()

        tracker = ExperimentTracker("test-exp")
        with patch("ml.experiments.tracker._get_mlflow", return_value=mock_mlflow):
            with tracker.start_run(run_name="test-run") as run_id:
                assert run_id == "abc123"

        mock_mlflow.start_run.assert_called_once()
        mock_mlflow.end_run.assert_called_once_with(status="FINISHED")


# ────────────────────────────────────────────────────────────────────────────
# E-3 · Model Registry
# ────────────────────────────────────────────────────────────────────────────


class TestModelRegistry:
    def test_save_creates_manifest(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("lstm", weights_root=tmpdir)
            version = reg.save(
                ticker="SPY",
                weight_path=Path(tmpdir) / "SPY.pt",
                metrics={"val_loss": 0.42},
                metadata={"train_start": "2023-01-01", "epochs": 20},
            )
            assert version == 1
            assert (Path(tmpdir) / "lstm" / "registry.json").exists()

    def test_save_increments_version(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("lstm", weights_root=tmpdir)
            v1 = reg.save("AAPL", Path(tmpdir) / "AAPL.pt")
            v2 = reg.save("AAPL", Path(tmpdir) / "AAPL.pt")
            assert v2 == v1 + 1

    def test_get_returns_entry(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("xgboost", weights_root=tmpdir)
            reg.save("TSLA", Path(tmpdir) / "TSLA.pt", metrics={"f1": 0.72})
            entry = reg.get("TSLA")
            assert entry is not None
            assert entry["ticker"] == "TSLA"
            assert entry["f1"] == 0.72

    def test_get_best_returns_minimum_loss(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("lstm", weights_root=tmpdir)
            reg.save("SPY", Path(tmpdir) / "SPY.pt", metrics={"val_loss": 0.5})
            reg.save("QQQ", Path(tmpdir) / "QQQ.pt", metrics={"val_loss": 0.3})
            reg.save("NVDA", Path(tmpdir) / "NVDA.pt", metrics={"val_loss": 0.8})
            best = reg.get_best("val_loss", mode="min")
            assert best is not None
            assert best["ticker"] == "QQQ"

    def test_delete_removes_entry(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("hmm", weights_root=tmpdir)
            reg.save("AMZN", Path(tmpdir) / "AMZN.pt")
            assert reg.delete("AMZN") is True
            assert reg.get("AMZN") is None

    def test_list_models_returns_all(self):
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg = ModelRegistry("lstm", weights_root=tmpdir)
            reg.save("SPY", Path(tmpdir) / "SPY.pt")
            reg.save("QQQ", Path(tmpdir) / "QQQ.pt")
            models = reg.list_models()
            tickers = {m["ticker"] for m in models}
            assert {"SPY", "QQQ"}.issubset(tickers)

    def test_manifest_persists_across_instances(self):
        """A new ModelRegistry instance reads the manifest saved by a previous one."""
        from ml.training.registry import ModelRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            reg1 = ModelRegistry("lstm", weights_root=tmpdir)
            reg1.save("META", Path(tmpdir) / "META.pt", metrics={"val_loss": 0.35})

            reg2 = ModelRegistry("lstm", weights_root=tmpdir)
            entry = reg2.get("META")
            assert entry is not None
            assert entry["val_loss"] == 0.35


# ────────────────────────────────────────────────────────────────────────────
# E-4 · TFT Model Architecture
# ────────────────────────────────────────────────────────────────────────────


class TestTFTModel:
    def test_forward_output_shape(self):
        import torch

        from ml.models.transformer.model import TFTModel

        model = TFTModel(n_features=12, d_model=32, n_heads=4, n_layers=2)
        x = torch.randn(8, 30, 12)  # (batch=8, seq=30, features=12)
        logits = model(x)
        assert logits.shape == (8, 3)

    def test_single_sample_inference(self):
        import torch

        from ml.models.transformer.model import TFTModel

        model = TFTModel(n_features=12, d_model=32, n_heads=4, n_layers=1)
        model.eval()
        with torch.no_grad():
            x = torch.randn(1, 20, 12)
            logits = model(x)
        assert logits.shape == (1, 3)

    def test_softmax_sums_to_one(self):
        import torch

        from ml.models.transformer.model import TFTModel

        model = TFTModel(n_features=12, d_model=32, n_heads=4, n_layers=1)
        model.eval()
        with torch.no_grad():
            x = torch.randn(4, 15, 12)
            probs = torch.softmax(model(x), dim=-1)
        assert torch.allclose(probs.sum(dim=-1), torch.ones(4), atol=1e-5)

    def test_d_model_not_divisible_by_n_heads_raises(self):
        from ml.models.transformer.model import TFTModel

        with pytest.raises(AssertionError):
            TFTModel(n_features=12, d_model=33, n_heads=4)

    def test_different_seq_lengths_work(self):
        """TFT must handle arbitrary sequence lengths."""
        import torch

        from ml.models.transformer.model import TFTModel

        model = TFTModel(n_features=8, d_model=32, n_heads=4, n_layers=1)
        model.eval()
        for seq in (5, 30, 100):
            with torch.no_grad():
                x = torch.randn(2, seq, 8)
                out = model(x)
            assert out.shape == (2, 3)

    def test_model_is_differentiable(self):
        """Gradients should flow through the model for training."""
        import torch

        from ml.models.transformer.model import TFTModel

        model = TFTModel(n_features=12, d_model=32, n_heads=4, n_layers=1)
        x = torch.randn(4, 20, 12)
        logits = model(x)
        loss = logits.mean()
        loss.backward()
        # All parameters should have gradients
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"
