"""
LSTM training script.

Fetches OHLCV data, builds dataset, trains the LSTMPricePredictor,
and saves model weights to disk (or S3 if AWS_S3_BUCKET is set).

Usage::

    from ml.models.lstm.train import train_lstm

    weight_path = train_lstm(
        ticker="SPY",
        start="2023-01-01",
        end="2024-01-01",
        epochs=20,
        hidden_size=64,
        seq_len=30,
    )
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

# Weights directory — uses data/ volume mount to avoid storing in source tree
_WEIGHTS_DIR = Path(
    os.environ.get("ML_WEIGHTS_DIR", "/app/data/ml_weights/lstm")
)


def _fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV data using yfinance (always available, no API key needed)."""
    import yfinance as yf  # noqa: PLC0415

    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker} {start}–{end}")
    df.columns = [c.lower() for c in df.columns]
    return df


def train_lstm(
    ticker: str,
    start: str,
    end: str,
    epochs: int = 20,
    hidden_size: int = 64,
    seq_len: int = 30,
    batch_size: int = 64,
    lr: float = 1e-3,
) -> Path:
    """
    Train the LSTM model on historical OHLCV data.

    Returns the path to the saved weights file.
    """
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, random_split  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("PyTorch is required for LSTM training") from exc

    import sys  # noqa: PLC0415
    _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

    from ml.experiments.tracker import ExperimentTracker  # noqa: PLC0415
    from ml.models.lstm.dataset import OHLCVDataset  # noqa: PLC0415
    from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415
    from ml.training.registry import ModelRegistry  # noqa: PLC0415

    df = _fetch_ohlcv(ticker, start, end)
    dataset = OHLCVDataset(df, seq_len=seq_len)

    if len(dataset) < 50:
        raise ValueError(
            f"Insufficient data for {ticker}: {len(dataset)} samples < 50 minimum"
        )

    # 80/20 train/val split
    n_val = max(1, int(len(dataset) * 0.2))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    device = torch.device("cpu")  # CPU training only; GPU if available
    model = LSTMPricePredictor(
        n_features=dataset.n_features,
        hidden_size=hidden_size,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    tracker = ExperimentTracker(f"LSTM-{ticker.upper()}")
    best_val_loss = float("inf")

    with tracker.start_run(
        run_name=f"lstm-{ticker.lower()}-e{epochs}",
        tags={"model": "lstm", "ticker": ticker.upper()},
    ) as run_id:
        tracker.log_params(
            {
                "ticker": ticker.upper(),
                "start": start,
                "end": end,
                "epochs": epochs,
                "hidden_size": hidden_size,
                "seq_len": seq_len,
                "batch_size": batch_size,
                "lr": lr,
            }
        )

        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for x_batch, y_batch in train_loader:
                x_batch = x_batch.to(device)
                y_batch = torch.tensor(y_batch, dtype=torch.long).to(device)
                optimizer.zero_grad()
                logits = model(x_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                train_loss += loss.item()

            # Validation loss
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for x_batch, y_batch in val_loader:
                    x_batch = x_batch.to(device)
                    y_batch = torch.tensor(y_batch, dtype=torch.long).to(device)
                    val_loss += criterion(model(x_batch), y_batch).item()

            train_loss /= max(len(train_loader), 1)
            val_loss /= max(len(val_loader), 1)
            tracker.log_metrics({"train_loss": train_loss, "val_loss": val_loss}, step=epoch)
            if val_loss < best_val_loss:
                best_val_loss = val_loss
            scheduler.step()

        # Save weights
        _WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        weight_path = _WEIGHTS_DIR / f"{ticker.upper()}.pt"
        torch.save(
            {
                "state_dict": model.state_dict(),
                "n_features": dataset.n_features,
                "hidden_size": hidden_size,
                "seq_len": seq_len,
                "ticker": ticker.upper(),
                "mean": dataset.X.mean(axis=0).tolist(),
                "std": (dataset.X.std(axis=0) + 1e-8).tolist(),
            },
            weight_path,
        )
        tracker.log_artifact(str(weight_path))

        # Register in the model registry
        reg = ModelRegistry("lstm")
        reg.save(
            ticker=ticker,
            weight_path=weight_path,
            metrics={"val_loss": best_val_loss},
            metadata={"train_start": start, "train_end": end, "epochs": epochs},
            mlflow_run_id=run_id,
        )

    # Upload to S3 if configured
    s3_bucket = os.environ.get("AWS_S3_BUCKET")
    if s3_bucket:
        try:
            import boto3  # noqa: PLC0415

            s3 = boto3.client("s3")
            s3_key = f"ml_weights/lstm/{ticker.upper()}.pt"
            s3.upload_file(str(weight_path), s3_bucket, s3_key)
        except Exception:  # noqa: BLE001
            pass  # S3 upload failure is non-fatal

    return weight_path
