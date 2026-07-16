"""
ML model endpoints — LSTM, XGBoost and HMM training + inference.

Endpoints:
  POST /ml/lstm/train              — dispatch LSTM training Celery task
  GET  /ml/lstm/predict?ticker=X   — LSTM inference (3-class probability)
  POST /ml/xgboost/train           — dispatch XGBoost training Celery task
  GET  /ml/xgboost/predict?ticker=X — XGBoost inference (binary signal + prob)
  GET  /ml/xgboost/features?ticker=X — XGBoost feature importance
  POST /ml/hmm/train               — dispatch HMM regime training Celery task
  GET  /ml/hmm/regime?ticker=X     — HMM regime detection inference
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import numpy as np
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


class HMMTrainRequest(BaseModel):
    ticker: str = Field("SPY", description="Ticker symbol")
    start_date: str = Field("2023-01-01", description="ISO date YYYY-MM-DD")
    end_date: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")
    n_components: int = Field(3, ge=2, le=10)


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


# ─── Composite AI score ───────────────────────────────────────────────────────


@router.get("/ai-score")
async def ai_score(ticker: str, _: CurrentUser):
    """Composite AI score: LSTM × 40 + XGBoost × 40 + FinBERT × 20 → 0–100."""
    sym = ticker.upper()
    reasoning: list[str] = []

    # Try LSTM up-probability (default 0.5 neutral on failure)
    lstm_up = 0.5
    try:
        from pathlib import Path  # noqa: PLC0415
        import torch  # noqa: PLC0415
        from ml.models.lstm.dataset import build_features, _FEATURE_COLS  # noqa: PLC0415
        from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415
        from datetime import date, timedelta  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        weight_path = Path(f"{_ML_WEIGHTS_DIR}/lstm/{sym}.pt")
        if weight_path.exists():
            checkpoint = torch.load(weight_path, map_location="cpu", weights_only=False)
            n_features = checkpoint["n_features"]
            hidden_size = checkpoint["hidden_size"]
            seq_len = checkpoint["seq_len"]
            mean = torch.tensor(checkpoint["mean"], dtype=torch.float32)
            std = torch.tensor(checkpoint["std"], dtype=torch.float32)

            model = LSTMPricePredictor(n_features=n_features, hidden_size=hidden_size)
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()

            end_date = date.today().isoformat()
            start_date = (date.today() - timedelta(days=365)).isoformat()
            df = yf.download(sym, start=start_date, end=end_date, auto_adjust=True, progress=False)
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                featured = build_features(df)
                cols = [c for c in _FEATURE_COLS if c in featured.columns]
                X = featured[cols].values[-seq_len:].astype("float32")
                if len(X) >= seq_len:
                    X_t = torch.tensor(X, dtype=torch.float32)
                    X_t = (X_t - mean[:len(cols)]) / std[:len(cols)]
                    X_t = X_t.unsqueeze(0)
                    probs = model.predict_proba(X_t).squeeze(0).tolist()
                    lstm_up = float(probs[2])  # index 2 = "up"
                    reasoning.append(f"LSTM: {lstm_up * 100:.1f}% up-probability")
        else:
            reasoning.append("LSTM: model not trained (using neutral 50%)")
    except Exception:  # noqa: BLE001
        reasoning.append("LSTM: inference unavailable (using neutral 50%)")

    # Try XGBoost long-probability (default 0.5 on failure)
    xgb_long = 0.5
    try:
        from ml.models.xgboost.model import XGBoostSignalClassifier, build_xgb_features  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415
        from datetime import date, timedelta  # noqa: PLC0415

        clf = XGBoostSignalClassifier.load(sym)
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=365)).isoformat()
        df = yf.download(sym, start=start_date, end=end_date, auto_adjust=True, progress=False)
        if not df.empty:
            df.columns = [c.lower() for c in df.columns]
            featured = build_xgb_features(df)
            result_xgb = clf.predict(featured)
            xgb_long = float(result_xgb["probability"])
            reasoning.append(f"XGBoost: {xgb_long * 100:.1f}% long-probability")
    except FileNotFoundError:
        reasoning.append("XGBoost: model not trained (using neutral 50%)")
    except Exception:  # noqa: BLE001
        reasoning.append("XGBoost: inference unavailable (using neutral 50%)")

    # Try FinBERT positive score (default 0.33 on failure)
    finbert_pos = 0.33
    finbert_neg = 0.33
    finbert_neu = 0.34
    try:
        from app.services.sentiment.finbert import score_text  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415

        info = yf.Ticker(sym).info
        headline = info.get("longBusinessSummary", f"{sym} stock")[:512]
        fb = score_text(headline)
        label = fb.get("label", "neutral")
        conf = float(fb.get("confidence", 0.33))
        if label == "bullish":
            finbert_pos = conf
            finbert_neg = (1 - conf) / 2
            finbert_neu = (1 - conf) / 2
        elif label == "bearish":
            finbert_neg = conf
            finbert_pos = (1 - conf) / 2
            finbert_neu = (1 - conf) / 2
        else:
            finbert_neu = conf
            finbert_pos = (1 - conf) / 2
            finbert_neg = (1 - conf) / 2
        reasoning.append(f"FinBERT: {label} (confidence {conf * 100:.1f}%)")
    except Exception:  # noqa: BLE001
        reasoning.append("FinBERT: sentiment unavailable (using neutral 33%)")

    # StockTwits social sentiment (default 0.5 neutral)
    st_bullish = 0.5
    try:
        from app.services.news.aggregator import get_stocktwits_stream  # noqa: PLC0415
        st_data = await get_stocktwits_stream(sym)
        st_bullish = float(st_data.get("bullish_pct", 0.5))
        tagged = st_data.get("tagged_count", 0)
        if tagged > 0:
            reasoning.append(f"StockTwits: {st_bullish * 100:.1f}% bullish ({tagged} tagged msgs)")
        else:
            reasoning.append("StockTwits: no tagged messages")
    except Exception:  # noqa: BLE001
        reasoning.append("StockTwits: unavailable (using neutral 50%)")

    # score = (lstm_up × 35 + xgb_long × 35 + finbert_pos × 15 + st_bullish × 15) → 0–100
    raw = lstm_up * 35.0 + xgb_long * 35.0 + finbert_pos * 15.0 + st_bullish * 15.0
    score = round(min(100.0, max(0.0, raw)), 1)

    if score > 60:
        signal = "bullish"
    elif score < 40:
        signal = "bearish"
    else:
        signal = "neutral"

    # Ensure we return at least 4 reasoning items
    while len(reasoning) < 4:
        reasoning.append("Insufficient data for additional factors")

    return {
        "ticker": sym,
        "score": score,
        "signal": signal,
        "reasoning": reasoning[:4],
        "components": {
            "lstm_up": round(lstm_up, 4),
            "xgb_long": round(xgb_long, 4),
            "finbert_positive": round(finbert_pos, 4),
            "finbert_negative": round(finbert_neg, 4),
            "finbert_neutral": round(finbert_neu, 4),
            "stocktwits_bullish": round(st_bullish, 4),
        },
    }


# ─── HMM endpoints ────────────────────────────────────────────────────────────


@router.post("/hmm/train")
async def train_hmm(payload: HMMTrainRequest, _: CurrentUser):
    """Dispatch an HMM regime-detection training job for the given ticker."""
    from app.tasks.ml_tasks import train_hmm_task  # noqa: PLC0415

    task = train_hmm_task.delay(
        ticker=payload.ticker,
        start=payload.start_date,
        end=payload.end_date,
        n_components=payload.n_components,
    )
    return {
        "task_id": str(task.id),
        "status": "queued",
        "ticker": payload.ticker,
    }


# Human-readable regime label mapping for n_components=3 endpoint.
# States are assigned after fitting by ranking mean volatility (col 0).
# We map label index 0→sideways, 1→bull, 2→bear by mean momentum ordering.
_HMM_3_LABELS = {0: "sideways", 1: "bull", 2: "bear"}


@router.get("/hmm/regime")
async def get_hmm_regime(
    ticker: str,
    _: CurrentUser,
):
    """Run HMM regime detection for the most recent bars of a ticker."""
    from pathlib import Path  # noqa: PLC0415

    ticker_upper = ticker.upper()
    model_path = Path(f"{_ML_WEIGHTS_DIR}/hmm/{ticker_upper}.pkl")

    if not model_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No HMM model trained for {ticker}. POST /ml/hmm/train first.",
        )

    try:
        import yfinance as yf  # noqa: PLC0415
        from datetime import date, timedelta  # noqa: PLC0415
        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        # Load the saved detector
        detector = RegimeDetector.load(model_path)

        # Fetch last 90 days of daily bars
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=90)).isoformat()
        df = yf.download(ticker_upper, start=start_date, end=end_date, auto_adjust=True, progress=False)
        if df.empty:
            raise HTTPException(status_code=502, detail=f"No market data for {ticker}")
        df.columns = [c.lower() for c in df.columns]

        # Build features: [volatility, spread, momentum] — same as train_hmm_task
        import pandas as pd  # noqa: PLC0415

        close = df["close"].astype(float)
        returns = close.pct_change().fillna(0.0)
        volatility = returns.rolling(20).std().fillna(0.0) * 100
        spread = np.zeros(len(df), dtype=float)
        momentum = close.pct_change(20).fillna(0.0)
        features = np.column_stack([volatility.values, spread, momentum.values])
        if len(features) > 20:
            features = features[20:]

        if len(features) == 0:
            raise HTTPException(status_code=422, detail="Insufficient data for regime detection")

        # Predict regime labels
        label_indices = detector.predict(features)
        last_label_idx = int(label_indices[-1])

        # Get per-state probabilities for the last bar
        proba = detector.predict_proba(features[-1:])  # shape (1, n_components)
        proba_row = proba[0].tolist()

        # Map label indices to human-readable strings
        n = detector.n_components
        label_map = _HMM_3_LABELS if n == 3 else {i: f"state_{i}" for i in range(n)}
        regime_str = label_map.get(last_label_idx, f"state_{last_label_idx}")

        # Build probabilities dict keyed by regime name
        probabilities = {
            label_map.get(i, f"state_{i}"): round(float(p), 4)
            for i, p in enumerate(proba_row)
        }

        return {
            "ticker": ticker_upper,
            "regime": regime_str,
            "probabilities": probabilities,
            "as_of": datetime.now(UTC).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ml.hmm.regime.error", ticker=ticker, error=str(exc))
        raise HTTPException(status_code=500, detail="HMM regime inference failed.") from exc


# ─── TFT endpoints ────────────────────────────────────────────────────────────


class TFTTrainRequest(BaseModel):
    ticker: str = Field("SPY", description="Ticker symbol")
    start: str = Field("2023-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-06-01", description="ISO date YYYY-MM-DD")
    epochs: int = Field(30, ge=1, le=200)
    d_model: int = Field(64, ge=16, le=512)
    n_heads: int = Field(4, ge=1, le=16)
    n_layers: int = Field(2, ge=1, le=8)
    seq_len: int = Field(30, ge=5, le=120)


@router.post("/transformer/train")
async def train_transformer_endpoint(body: TFTTrainRequest, current_user: CurrentUser):
    """
    Dispatch a TFT training job for the given ticker.

    Training runs as a Celery task and logs to MLflow (when configured).
    Returns task_id for status polling.
    """
    from app.tasks.ml_tasks import train_transformer_task  # noqa: PLC0415

    task = train_transformer_task.delay(
        ticker=body.ticker,
        start=body.start,
        end=body.end,
        epochs=body.epochs,
        d_model=body.d_model,
        n_heads=body.n_heads,
        n_layers=body.n_layers,
        seq_len=body.seq_len,
    )
    return {
        "task_id": task.id,
        "status": "queued",
        "ticker": body.ticker,
        "model": "transformer",
    }


@router.get("/transformer/predict")
async def predict_transformer(
    current_user: CurrentUser,
    ticker: str = Query("SPY", description="Ticker symbol"),
    seq_len: int = Query(30, ge=5, le=120),
):
    """
    Run TFT inference for the given ticker.

    Returns 3-class probability vector: bearish / neutral / bullish.
    Falls back to equal probabilities when no trained model exists.
    """
    try:
        import torch  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from ml.feature_store.store import compute_features  # noqa: PLC0415
        from ml.models.transformer.model import TFTModel  # noqa: PLC0415

        ticker_upper = ticker.upper()
        weight_dir = os.path.join(_ML_WEIGHTS_DIR, "..", "transformer")
        weight_path = os.path.join(weight_dir, f"{ticker_upper}.pt")

        if not os.path.exists(weight_path):
            return {
                "ticker": ticker_upper,
                "probabilities": {"bearish": 0.333, "neutral": 0.334, "bullish": 0.333},
                "predicted_class": "neutral",
                "note": "No trained model; returning uniform priors.",
                "as_of": datetime.now(UTC).isoformat(),
            }

        checkpoint = torch.load(weight_path, map_location="cpu", weights_only=True)
        model = TFTModel(
            n_features=checkpoint["n_features"],
            d_model=checkpoint.get("d_model", 64),
            n_heads=checkpoint.get("n_heads", 4),
            n_layers=checkpoint.get("n_layers", 2),
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        end_date = datetime.now(UTC).strftime("%Y-%m-%d")
        start_date = f"{int(end_date[:4]) - 1}{end_date[4:]}"
        df = yf.download(ticker_upper, start=start_date, end=end_date, auto_adjust=True, progress=False)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No market data for {ticker_upper}")
        df.columns = [c.lower() for c in df.columns]

        # Compute feature sequence
        feat_seq = []
        for i in range(max(30, seq_len), len(df)):
            window = df.iloc[max(0, i - 200) : i + 1]
            feats = compute_features(window)
            if feats:
                feat_seq.append(list(feats.values()))

        if len(feat_seq) < seq_len:
            raise HTTPException(status_code=422, detail="Insufficient data for inference")

        feat_arr = np.array(feat_seq[-seq_len:], dtype=np.float32)
        feat_mean = np.array(checkpoint.get("feat_mean", [0.0] * feat_arr.shape[-1]))
        feat_std = np.array(checkpoint.get("feat_std", [1.0] * feat_arr.shape[-1]))
        feat_arr = (feat_arr - feat_mean) / (feat_std + 1e-8)

        x = torch.from_numpy(feat_arr).unsqueeze(0)  # (1, seq_len, n_features)
        with torch.no_grad():
            logits = model(x)
            probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()

        label_map = {0: "bearish", 1: "neutral", 2: "bullish"}
        pred_class = label_map[int(np.argmax(probs))]

        return {
            "ticker": ticker_upper,
            "probabilities": {
                "bearish": round(probs[0], 4),
                "neutral": round(probs[1], 4),
                "bullish": round(probs[2], 4),
            },
            "predicted_class": pred_class,
            "as_of": datetime.now(UTC).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ml.transformer.predict.error", ticker=ticker, error=str(exc))
        raise HTTPException(status_code=500, detail="TFT inference failed.") from exc


@router.get("/registry")
async def list_model_registry(current_user: CurrentUser):
    """
    Return all registered model versions across all model types.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    ))))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from ml.training.registry import ModelRegistry  # noqa: PLC0415

    result = {}
    for model_type in ("lstm", "xgboost", "hmm", "transformer"):
        reg = ModelRegistry(model_type)
        result[model_type] = reg.list_models()
    return result
