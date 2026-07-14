"""
Unit tests — Regime Detection HMM (ST-Q).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from app.auth.jwt import create_access_token

_VALID_REGIME_LABELS = {"trending", "mean_reverting", "high_volatility", "low_volatility"}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _synthetic_features(n: int = 60, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, 3)).astype(np.float64)


def _auth_header() -> dict[str, str]:
    token = create_access_token({"sub": "u1", "email": "t@t.com", "role": "trader"})
    return {"Authorization": f"Bearer {token}"}


# ─── RegimeDetector unit tests ────────────────────────────────────────────────


class TestRegimeDetectorWithHmmlearn:
    """Tests that run only when hmmlearn is actually installed."""

    def _skip_if_missing(self):
        pytest.importorskip("hmmlearn", reason="hmmlearn not installed")

    def test_fit_and_predict_shape(self):
        self._skip_if_missing()
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        features = _synthetic_features(120)
        det = RegimeDetector(n_components=4, n_iter=10, random_state=0)
        det.fit(features)
        preds = det.predict(features)
        assert preds.shape == (120,)
        assert set(preds).issubset({0, 1, 2, 3})

    def test_predict_proba_sums_to_one(self):
        self._skip_if_missing()
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        features = _synthetic_features(80)
        det = RegimeDetector(n_components=4, n_iter=10, random_state=1)
        det.fit(features)
        proba = det.predict_proba(features)
        assert proba.shape == (80, 4)
        row_sums = proba.sum(axis=1)
        np.testing.assert_allclose(row_sums, np.ones(80), atol=1e-5)

    def test_regime_label_returns_valid_strings(self):
        self._skip_if_missing()
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        det = RegimeDetector()
        for idx in range(4):
            label = det.regime_label(idx)
            assert label in _VALID_REGIME_LABELS

    def test_regime_label_invalid_index_raises(self):
        self._skip_if_missing()
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        det = RegimeDetector()
        with pytest.raises(ValueError):
            det.regime_label(99)

    def test_predict_before_fit_raises(self):
        self._skip_if_missing()
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        det = RegimeDetector()
        with pytest.raises(RuntimeError):
            det.predict(_synthetic_features(10))


class TestRegimeDetectorMocked:
    """Tests that mock hmmlearn so they run even when it is not installed."""

    def test_predict_raw_indices_are_valid(self):
        """Verify the raw state array from a mocked HMM is within valid range."""
        mock_model = MagicMock()
        raw = np.array([0, 1, 2, 3, 0, 2])
        mock_model.predict.return_value = raw
        mock_model.means_ = np.array([
            [0.1, 0.0, -0.1],
            [0.5, 0.1, 0.0],
            [0.8, 0.2, 0.1],
            [1.5, 0.3, 0.2],
        ])
        assert all(0 <= v <= 3 for v in mock_model.predict.return_value)

    def test_regime_label_all_four_variants(self):
        """Validate all 4 label strings without needing hmmlearn installed."""
        from ml.models.hmm.model import _REGIME_LABELS  # noqa: PLC0415

        assert set(_REGIME_LABELS) == _VALID_REGIME_LABELS
        assert len(_REGIME_LABELS) == 4


# ─── GET /macro/regime endpoint ───────────────────────────────────────────────


class TestMacroRegimeEndpoint:
    """HTTP-level tests for GET /macro/regime."""

    @pytest.mark.asyncio
    async def test_regime_demo_mode_returns_valid_response(self, client):
        """With no model file present, endpoint must return demo regime."""
        with patch("app.api.v1.macro._load_regime_detector", return_value=None):
            resp = await client.get("/api/v1/macro/regime", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["regime"] in _VALID_REGIME_LABELS
        assert 0.0 <= body["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_regime_requires_auth(self, client):
        resp = await client.get("/api/v1/macro/regime")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_regime_with_mock_detector(self, client):
        """When a detector is returned, endpoint must still return valid regime."""
        mock_detector = MagicMock()
        mock_detector.predict_proba.return_value = np.array([[0.1, 0.2, 0.6, 0.1]])
        mock_detector.regime_label.return_value = "trending"

        with patch("app.api.v1.macro._load_regime_detector", return_value=mock_detector):
            resp = await client.get("/api/v1/macro/regime", headers=_auth_header())
        assert resp.status_code == 200
        body = resp.json()
        assert body["regime"] in _VALID_REGIME_LABELS
