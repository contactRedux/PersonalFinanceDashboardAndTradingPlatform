"""
TFT (Temporal Fusion Transformer) training script.

Integrates with:
  - Feature store (ml.feature_store.store) for feature computation
  - Experiment tracker (ml.experiments.tracker) for MLflow logging
  - Model registry (ml.training.registry) for weight versioning

Phase 1: uses OHLCV bars fetched via yfinance (no tick data required).
Phase 2 (future): replaces yfinance with tick-replay OHLCV from TimescaleDB
          once sufficient tick volume is confirmed in production.

Usage::

    from ml.models.transformer.train import train_transformer

    weight_path = train_transformer(
        ticker="SPY",
        start="2023-01-01",
        end="2024-06-01",
        epochs=30,
    )
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_WEIGHTS_DIR = Path(os.environ.get("ML_WEIGHTS_DIR", "/app/data/ml_weights/transformer"))


def _fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf  # noqa: PLC0415

    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker} {start}–{end}")
    df.columns = [c.lower() for c in df.columns]
    return df


def _build_dataset(df: pd.DataFrame, seq_len: int = 30):
    """
    Build a supervised dataset from OHLCV + computed features.

    Returns
    -------
    X : np.ndarray of shape (N, seq_len, n_features)
    y : np.ndarray of shape (N,)
        0 = bearish (next-day return < -0.5%)
        1 = neutral
        2 = bullish (next-day return > +0.5%)
    """
    from ml.feature_store.store import compute_features  # noqa: PLC0415

    # Compute rolling features by appending one row at a time to keep it
    # simple — vectorised window computation
    close = df["close"].values.astype(np.float32)
    high = df["high"].values.astype(np.float32)
    low = df["low"].values.astype(np.float32)
    volume = df["volume"].values.astype(np.float32)

    n = len(df)
    feature_rows: list[list[float]] = []

    for i in range(min(200, n), n):
        window = df.iloc[max(0, i - 200) : i + 1]
        feats = compute_features(window)
        if not feats:
            feature_rows.append([0.0] * 12)
        else:
            feature_rows.append(list(feats.values()))

    if len(feature_rows) < seq_len + 1:
        raise ValueError(f"Insufficient feature rows: {len(feature_rows)}")

    feat_arr = np.array(feature_rows, dtype=np.float32)

    # Normalise features to zero mean, unit std (prevent gradient explosion)
    mean = feat_arr.mean(axis=0)
    std = feat_arr.std(axis=0) + 1e-8
    feat_arr = (feat_arr - mean) / std

    n_feat = len(feature_rows)
    start_idx = min(200, n)
    close_feat = close[start_idx:]  # aligns with feature_rows

    X, y = [], []
    for i in range(seq_len, n_feat - 1):
        X.append(feat_arr[i - seq_len : i])
        # Label: next-bar return
        ret = (close_feat[i + 1] - close_feat[i]) / (close_feat[i] + 1e-8)
        if ret > 0.005:
            label = 2  # bullish
        elif ret < -0.005:
            label = 0  # bearish
        else:
            label = 1  # neutral
        y.append(label)

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64), mean, std


def train_transformer(
    ticker: str,
    start: str,
    end: str,
    epochs: int = 30,
    d_model: int = 64,
    n_heads: int = 4,
    n_layers: int = 2,
    seq_len: int = 30,
    batch_size: int = 64,
    lr: float = 1e-3,
    dropout: float = 0.1,
    use_mlflow: bool = True,
    use_registry: bool = True,
) -> Path:
    """
    Train the TFT model on historical OHLCV data.

    Returns the path to the saved weights file.
    """
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset, random_split  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("PyTorch is required for TFT training") from exc

    from ml.experiments.tracker import ExperimentTracker  # noqa: PLC0415
    from ml.models.transformer.model import TFTModel  # noqa: PLC0415
    from ml.training.registry import ModelRegistry  # noqa: PLC0415

    df = _fetch_ohlcv(ticker, start, end)
    X, y, feat_mean, feat_std = _build_dataset(df, seq_len=seq_len)

    n_features = X.shape[-1]
    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y)

    dataset = TensorDataset(X_t, y_t)
    n_val = max(1, int(len(dataset) * 0.2))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    device = torch.device("cpu")
    model = TFTModel(
        n_features=n_features,
        d_model=d_model,
        n_heads=n_heads,
        n_layers=n_layers,
        dropout=dropout,
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    tracker = ExperimentTracker(f"TFT-{ticker.upper()}")
    run_context = (
        tracker.start_run(
            run_name=f"tft-{ticker.lower()}-e{epochs}",
            tags={"model": "tft", "ticker": ticker.upper()},
        )
        if use_mlflow
        else _noop_context()
    )

    best_val_loss = float("inf")
    best_epoch = 0

    with run_context as run_id:
        if use_mlflow:
            tracker.log_params(
                {
                    "ticker": ticker.upper(),
                    "start": start,
                    "end": end,
                    "epochs": epochs,
                    "d_model": d_model,
                    "n_heads": n_heads,
                    "n_layers": n_layers,
                    "seq_len": seq_len,
                    "batch_size": batch_size,
                    "lr": lr,
                }
            )

        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for xb, yb in train_loader:
                xb, yb = xb.to(device), yb.to(device)
                optimizer.zero_grad()
                logits = model(xb)
                loss = criterion(logits, yb)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                train_loss += loss.item()

            # Validation
            model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    logits = model(xb)
                    val_loss += criterion(logits, yb).item()
                    pred = logits.argmax(dim=1)
                    correct += (pred == yb).sum().item()
                    total += yb.size(0)

            train_loss /= max(len(train_loader), 1)
            val_loss /= max(len(val_loader), 1)
            val_acc = correct / max(total, 1)
            scheduler.step()

            if use_mlflow:
                tracker.log_metrics(
                    {"train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc},
                    step=epoch,
                )

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch

            logger.debug(
                "tft.epoch",
                ticker=ticker,
                epoch=epoch + 1,
                train_loss=round(train_loss, 4),
                val_loss=round(val_loss, 4),
                val_acc=round(val_acc, 3),
            )

        # Save weights
        _WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        weight_path = _WEIGHTS_DIR / f"{ticker.upper()}.pt"
        torch.save(
            {
                "state_dict": model.state_dict(),
                "n_features": n_features,
                "d_model": d_model,
                "n_heads": n_heads,
                "n_layers": n_layers,
                "seq_len": seq_len,
                "ticker": ticker.upper(),
                "feat_mean": feat_mean.tolist(),
                "feat_std": feat_std.tolist(),
            },
            weight_path,
        )

        if use_mlflow:
            tracker.log_artifact(str(weight_path))

        # Register in the model registry
        if use_registry:
            reg = ModelRegistry("transformer")
            reg.save(
                ticker=ticker,
                weight_path=weight_path,
                metrics={"val_loss": best_val_loss},
                metadata={
                    "train_start": start,
                    "train_end": end,
                    "best_epoch": best_epoch,
                    "epochs": epochs,
                },
                mlflow_run_id=run_id,
            )

    logger.info(
        "tft.training_complete",
        ticker=ticker,
        best_val_loss=round(best_val_loss, 4),
        weight_path=str(weight_path),
    )
    return weight_path


from contextlib import contextmanager  # noqa: E402


@contextmanager
def _noop_context():
    """Context manager that yields None and does nothing."""
    yield None
