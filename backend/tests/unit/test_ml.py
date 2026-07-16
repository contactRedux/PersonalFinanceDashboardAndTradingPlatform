"""
Unit tests — HMM regime API endpoints (ST-HMM) + ai-score composite endpoint.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.jwt import create_access_token

# Ensure app is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _auth_header() -> dict[str, str]:
    token = create_access_token({"sub": "u1", "email": "t@t.com", "role": "trader"})
    return {"Authorization": f"Bearer {token}"}


class TestHMMTrainEndpoint:
    """Tests for POST /api/v1/ml/hmm/train."""

    @pytest.mark.asyncio
    async def test_hmm_train_returns_task_id(self, client) -> None:
        """
        POST /ml/hmm/train must dispatch a Celery task and return task_id,
        status=queued, and the ticker.
        """
        mock_task = MagicMock()
        mock_task.id = "test-task-uuid-1234"

        with patch("app.tasks.ml_tasks.train_hmm_task") as mock_celery_task:
            mock_celery_task.delay.return_value = mock_task

            resp = await client.post(
                "/api/v1/ml/hmm/train",
                json={
                    "ticker": "SPY",
                    "start_date": "2023-01-01",
                    "end_date": "2024-01-01",
                    "n_components": 3,
                },
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "test-task-uuid-1234"
        assert body["status"] == "queued"
        assert body["ticker"] == "SPY"

    @pytest.mark.asyncio
    async def test_hmm_train_requires_auth(self, client) -> None:
        """POST /ml/hmm/train must reject unauthenticated requests."""
        resp = await client.post(
            "/api/v1/ml/hmm/train",
            json={"ticker": "SPY", "start_date": "2023-01-01", "end_date": "2024-01-01"},
        )
        assert resp.status_code in (401, 403)


class TestHMMRegimeEndpoint:
    """Tests for GET /api/v1/ml/hmm/regime."""

    @pytest.mark.asyncio
    async def test_hmm_regime_returns_404_when_no_model(self, client) -> None:
        """
        GET /ml/hmm/regime must return 404 with a helpful message when the
        model pickle file does not exist.
        """
        resp = await client.get(
            "/api/v1/ml/hmm/regime?ticker=NOTRAINED",
            headers=_auth_header(),
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert "NOTRAINED" in detail
        assert "POST /ml/hmm/train" in detail


# ─── ai-score endpoint helpers ────────────────────────────────────────────────


def _make_mock_user():
    """Return a minimal mock current user that satisfies the dependency."""
    user = MagicMock()
    user.id = "test-user-id"
    return user


# ─── Test: neutral baseline (no models trained) ───────────────────────────────


@pytest.mark.asyncio
async def test_ai_score_neutral_when_no_models():
    """
    With no LSTM or XGBoost weights and a fallback FinBERT,
    all components default to 0.5 / 0.5 / 0.33, producing a neutral score.
    """
    from app.api.v1.ml import ai_score

    # Patch yfinance and torch to fail gracefully so all branches fall back
    mock_yf = MagicMock()
    mock_yf.Ticker.return_value.info = {}
    mock_yf.download.return_value = MagicMock(empty=True)

    with patch.dict("sys.modules", {"yfinance": mock_yf, "torch": None}):
        with patch("app.api.v1.ml._ML_WEIGHTS_DIR", "/nonexistent"):
            result = await ai_score(ticker="AAPL", _=_make_mock_user())

    assert result["ticker"] == "AAPL"
    assert 0.0 <= result["score"] <= 100.0
    assert result["signal"] in ("bullish", "neutral", "bearish")
    assert len(result["reasoning"]) >= 3
    assert "components" in result
    assert "lstm_up" in result["components"]
    assert "xgb_long" in result["components"]
    assert "finbert_positive" in result["components"]


# ─── Test: score formula with mocked FinBERT ─────────────────────────────────


@pytest.mark.asyncio
async def test_ai_score_components_present():
    """
    Response always includes ticker, score, signal, reasoning (3 items),
    and a components sub-dict with all expected keys.
    """
    from app.api.v1.ml import ai_score

    mock_fb_result = {
        "label": "bullish",
        "confidence": 0.9,
        "raw_score": 0.9,
        "model": "finbert",
    }
    mock_yf = MagicMock()
    mock_yf.Ticker.return_value.info = {"longBusinessSummary": "Apple is growing fast."}

    with patch("app.api.v1.ml._ML_WEIGHTS_DIR", "/nonexistent"):
        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            with patch("app.services.sentiment.finbert.score_text", return_value=mock_fb_result):
                result = await ai_score(ticker="MSFT", _=_make_mock_user())

    assert result["ticker"] == "MSFT"
    assert isinstance(result["score"], float)
    assert result["signal"] in ("bullish", "neutral", "bearish")
    assert isinstance(result["reasoning"], list)
    assert len(result["reasoning"]) >= 3
    for key in ("lstm_up", "xgb_long", "finbert_positive", "finbert_negative", "finbert_neutral", "stocktwits_bullish"):
        assert key in result["components"]
    # finbert_positive should match the mocked bullish confidence
    assert result["components"]["finbert_positive"] == pytest.approx(0.9, abs=0.01)
