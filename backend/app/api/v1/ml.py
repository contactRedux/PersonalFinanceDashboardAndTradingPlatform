"""
ML model endpoints — LSTM and XGBoost training + inference.

Endpoints:
  POST /ml/lstm/train              — dispatch LSTM training Celery task
  GET  /ml/lstm/predict?ticker=X   — LSTM inference (3-class probability)
  POST /ml/xgboost/train           — dispatch XGBoost training Celery task
  GET  /ml/xgboost/predict?ticker=X — XGBoost inference (binary signal + prob)
  GET  /ml/xgboost/features?ticker=X — XGBoost feature importance
"""

from __future__ import annotations

import os
import sys

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter()

# Ensure ml package is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ML_WEIGHTS_DIR = os.environ.get("ML_WEIGHTS_DIR", "/app/data/ml_weights")


# ─── Schemas ──────────────────────────────────────────────────────────────────


class LSTMTrainRequest(BaseModel):
    ticker: str = Field("SPY", description="Ticker symbol")
    start: str = Field("2023-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")
    epochs: int = Field(20, ge=1, le=200)
    hidden_size: int = Field(64, ge=16, le=512)
    seq_len: int = Field(30, ge=5, le=120)


class XGBoostTrainRequest(BaseModel):
    ticker: str = Field("SPY", description="Ticker symbol")
    start: str = Field("2023-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")


# ─── LSTM endpoints ───────────────────────────────────────────────────────────


@router.post("/lstm/train")
async def train_lstm(body: LSTMTrainRequest, current_user: CurrentUser):
    """
    Dispatch an LSTM training job for the given ticker.

    Training runs as a Celery task. Returns task_id for status polling.
    """
    from app.tasks.ml_tasks import train_lstm_task  # noqa: PLC0415

    task = train_lstm_task.delay(
        ticker=body.ticker,
        start=body.start,
        end=body.end,
        epochs=body.epochs,
        hidden_size=body.hidden_size,
        seq_len=body.seq_len,
    )
    return {
        "task_id": task.id,
        "ticker": body.ticker,
        "status": "queued",
        "message": f"LSTM training for {body.ticker} dispatched. Poll /celery/tasks/{task.id} for status.",
    }


@router.get("/lstm/predict")
async def predict_lstm(
    current_user: CurrentUser,
    ticker: str = Query(..., description="Ticker symbol"),
):
    """
    Run LSTM inference for the most recent bars of a ticker.

    Loads the latest saved weights and returns 3-class probabilities.
    """
    import torch  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    weight_path = Path(f"{_ML_WEIGHTS_DIR}/lstm/{ticker.upper()}.pt")
    if not weight_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trained LSTM model found for {ticker}. Run POST /ml/lstm/train first.",
        )

    try:
        import yfinance as yf  # noqa: PLC0415
        from ml.models.lstm.dataset import OHLCVDataset, build_features, _FEATURE_COLS  # noqa: PLC0415
        from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415

        # Load checkpoint
        checkpoint = torch.load(weight_path, map_location="cpu", weights_only=False)
        n_features = checkpoint["n_features"]
        hidden_size = checkpoint["hidden_size"]
        seq_len = checkpoint["seq_len"]
        mean = torch.tensor(checkpoint["mean"], dtype=torch.float32)
        std = torch.tensor(checkpoint["std"], dtype=torch.float32)

        model = LSTMPricePredictor(n_features=n_features, hidden_size=hidden_size)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        # Fetch recent data
        import pandas as pd  # noqa: PLC0415
        from datetime import date, timedelta  # noqa: PLC0415

        end = date.today().isoformat()
        start = (date.today() - timedelta(days=365)).isoformat()
        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            raise HTTPException(status_code=502, detail=f"No market data for {ticker}")
        df.columns = [c.lower() for c in df.columns]

        featured = build_features(df)
        cols = [c for c in _FEATURE_COLS if c in featured.columns]
        X = featured[cols].values[-seq_len:].astype("float32")

        if len(X) < seq_len:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient data: need {seq_len} bars, got {len(X)}",
            )

        # Normalise
        X_t = torch.tensor(X, dtype=torch.float32)
        X_t = (X_t - mean[:len(cols)]) / std[:len(cols)]
        X_t = X_t.unsqueeze(0)  # (1, seq_len, n_features)

        probs = model.predict_proba(X_t).squeeze(0).tolist()
        pred_class = int(probs.index(max(probs)))
        labels = ["down", "flat", "up"]

        return {
            "ticker": ticker.upper(),
            "prediction": labels[pred_class],
            "confidence": round(max(probs), 4),
            "probabilities": {
                "down": round(probs[0], 4),
                "flat": round(probs[1], 4),
                "up": round(probs[2], 4),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ml.lstm.predict.error", ticker=ticker, error=str(exc))
        raise HTTPException(status_code=500, detail="LSTM inference failed.") from exc


# ─── XGBoost endpoints ────────────────────────────────────────────────────────


@router.post("/xgboost/train")
async def train_xgboost(body: XGBoostTrainRequest, current_user: CurrentUser):
    """Dispatch an XGBoost training job for the given ticker."""
    from app.tasks.ml_tasks import train_xgboost_task  # noqa: PLC0415

    task = train_xgboost_task.delay(
        ticker=body.ticker,
        start=body.start,
        end=body.end,
    )
    return {
        "task_id": task.id,
        "ticker": body.ticker,
        "status": "queued",
        "message": f"XGBoost training for {body.ticker} dispatched.",
    }


@router.get("/xgboost/predict")
async def predict_xgboost(
    current_user: CurrentUser,
    ticker: str = Query(..., description="Ticker symbol"),
):
    """Run XGBoost inference for the most recent bars of a ticker."""
    try:
        import yfinance as yf  # noqa: PLC0415
        from datetime import date, timedelta  # noqa: PLC0415
        from ml.models.xgboost.model import XGBoostSignalClassifier, build_xgb_features  # noqa: PLC0415

        clf = XGBoostSignalClassifier.load(ticker)

        end = date.today().isoformat()
        start = (date.today() - timedelta(days=365)).isoformat()
        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            raise HTTPException(status_code=502, detail=f"No market data for {ticker}")
        df.columns = [c.lower() for c in df.columns]

        featured = build_xgb_features(df)
        result = clf.predict(featured)
        signal_label = "long" if result["signal"] == 1 else "no-position"

        return {
            "ticker": ticker.upper(),
            "signal": signal_label,
            "probability": result["probability"],
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No trained XGBoost model for {ticker}. Run POST /ml/xgboost/train first.",
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ml.xgboost.predict.error", ticker=ticker, error=str(exc))
        raise HTTPException(status_code=500, detail="XGBoost inference failed.") from exc


@router.get("/xgboost/features")
async def xgboost_feature_importance(
    current_user: CurrentUser,
    ticker: str = Query(..., description="Ticker symbol"),
):
    """Return feature importance ranking for a trained XGBoost model."""
    try:
        from ml.models.xgboost.model import XGBoostSignalClassifier  # noqa: PLC0415

        clf = XGBoostSignalClassifier.load(ticker)
        importance = clf.get_feature_importance()
        return {
            "ticker": ticker.upper(),
            "feature_importance": importance,
            "count": len(importance),
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No trained XGBoost model for {ticker}.",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Feature importance retrieval failed.") from exc
