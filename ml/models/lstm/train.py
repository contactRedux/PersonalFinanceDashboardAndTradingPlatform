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

    from ml.models.lstm.dataset import OHLCVDataset  # noqa: PLC0415
    from ml.models.lstm.model import LSTMPricePredictor  # noqa: PLC0415

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
