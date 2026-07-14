"""
ML model training and inference Celery tasks.

Runs in the Celery worker process (separate from FastAPI) so heavy training
does not block the API.
"""

from __future__ import annotations

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="tasks.train_lstm", bind=True, max_retries=1, default_retry_delay=60)
def train_lstm_task(
    self,
    ticker: str,
    start: str,
    end: str,
    epochs: int = 20,
    hidden_size: int = 64,
    seq_len: int = 30,
) -> dict:
    """
    Train the LSTM price predictor for a single ticker.

    Returns the path to the saved weights file.
    """
    try:
        import sys  # noqa: PLC0415
        import os  # noqa: PLC0415

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from ml.models.lstm.train import train_lstm  # noqa: PLC0415

        weight_path = train_lstm(
            ticker=ticker,
            start=start,
            end=end,
            epochs=epochs,
            hidden_size=hidden_size,
            seq_len=seq_len,
        )
        logger.info("tasks.train_lstm.done", ticker=ticker, path=str(weight_path))
        return {"status": "done", "ticker": ticker, "weight_path": str(weight_path)}
    except Exception as exc:  # noqa: BLE001
        logger.error("tasks.train_lstm.error", ticker=ticker, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "ticker": ticker, "error": str(exc)}


@celery_app.task(name="tasks.train_hmm", bind=True, max_retries=1, default_retry_delay=60)
def train_hmm_task(
    self,
    ticker: str,
    start: str,
    end: str,
    n_components: int = 3,
) -> dict:
    """Train the HMM regime detector for a single ticker."""
    try:
        import os  # noqa: PLC0415
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        import numpy as np  # noqa: PLC0415
        import yfinance as yf  # noqa: PLC0415

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from ml.models.hmm.model import RegimeDetector  # noqa: PLC0415

        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for {ticker}")
        df.columns = [c.lower() for c in df.columns]

        close = df["close"].astype(float)
        returns = close.pct_change().fillna(0.0)
        volatility = returns.rolling(20).std().fillna(0.0) * 100
        spread = np.zeros(len(df), dtype=float)
        momentum = close.pct_change(20).fillna(0.0)
        features = np.column_stack([volatility.values, spread, momentum.values])
        features = features[20:] if len(features) > 20 else features
        if len(features) < max(30, n_components * 10):
            raise ValueError(f"Insufficient data to train HMM for {ticker}")

        detector = RegimeDetector(n_components=n_components, n_iter=100, random_state=42)
        detector.fit(features)

        weights_root = Path(os.environ.get("ML_WEIGHTS_DIR", "/app/data/ml_weights"))
        model_dir = weights_root / "hmm"
        model_dir.mkdir(parents=True, exist_ok=True)
        weight_path = model_dir / f"{ticker.upper()}.pkl"
        detector.save(weight_path)

        logger.info("tasks.train_hmm.done", ticker=ticker, path=str(weight_path))
        return {"status": "done", "ticker": ticker, "weight_path": str(weight_path)}
    except Exception as exc:  # noqa: BLE001
        logger.error("tasks.train_hmm.error", ticker=ticker, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "ticker": ticker, "error": str(exc)}


@celery_app.task(name="tasks.train_xgboost", bind=True, max_retries=1, default_retry_delay=60)
def train_xgboost_task(
    self,
    ticker: str,
    start: str,
    end: str,
) -> dict:
    """Train the XGBoost signal classifier for a single ticker."""
    try:
        import sys  # noqa: PLC0415
        import os  # noqa: PLC0415

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        import yfinance as yf  # noqa: PLC0415
        from ml.models.xgboost.model import (  # noqa: PLC0415
            XGBoostSignalClassifier,
            build_xgb_features,
            _LABEL_THRESHOLD,
            _LABEL_HORIZON,
        )

        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"No data returned for {ticker}")
        df.columns = [c.lower() for c in df.columns]

        featured = build_xgb_features(df)
        featured["label"] = (featured["fwd_return_5"] > _LABEL_THRESHOLD).astype(int)
        # Drop fwd_return_5 to avoid data leakage
        featured = featured.drop(columns=["fwd_return_5"], errors="ignore")

        classifier = XGBoostSignalClassifier()
        classifier.train(featured, label_col="label")
        weight_path = classifier.save(ticker)

        logger.info("tasks.train_xgboost.done", ticker=ticker, path=str(weight_path))
        return {"status": "done", "ticker": ticker, "weight_path": str(weight_path)}
    except Exception as exc:  # noqa: BLE001
        logger.error("tasks.train_xgboost.error", ticker=ticker, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "ticker": ticker, "error": str(exc)}
