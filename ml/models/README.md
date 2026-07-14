# ml/models — Individual ML Model Implementations

## What is this folder?

Each subfolder here is one complete machine learning model: its architecture, training script, and dataset preparation. Think of each subfolder as a separate specialized analyst — the LSTM analyst studies price sequences, the XGBoost analyst studies feature tables, the HMM analyst studies market conditions.

---

## `lstm/` — LSTM Price Direction Predictor

**Three files:**

**`model.py`** — Defines **`LSTMPricePredictor`** — the neural network architecture (a PyTorch `nn.Module`). Two stacked LSTM layers feed into a linear classification head with 3 outputs (down / flat / up). The `forward(x)` method processes a sequence of shape `(batch, seq_len, n_features)` and returns raw logits; `predict_proba(x)` applies softmax to convert to probabilities.

**`dataset.py`** — The **`build_features(df)`** function computes all technical indicator features from an OHLCV DataFrame. This is the shared feature pipeline for both LSTM and XGBoost. Also contains the `PriceDataset` PyTorch Dataset class that converts the feature DataFrame into fixed-length sequences (windows) of `seq_len` bars.

**`train.py`** — The **`train_lstm(ticker, start, end, epochs, hidden_size, seq_len)`** function: downloads price data (via yfinance), builds features, creates train/validation splits (80/20), trains the model with Adam optimizer and cross-entropy loss, and saves the best weights (lowest validation loss) to `data/ml_weights/lstm/{TICKER}.pt`.

---

## `xgboost/` — XGBoost Binary Signal Classifier

**One file: `model.py`**

**`build_xgb_features(df)`** — Calls `lstm/dataset.py`'s `build_features()` (reusing the shared pipeline) then adds **lagged returns** (price changes 1, 3, 5, and 10 bars ago). Also computes the forward 5-bar return as a label (>1% = 1, otherwise = 0), which is dropped from the feature matrix before training to prevent data leakage (using tomorrow's information today).

**`XGBoostSignalClassifier`** — The main class:
- **`train(df, label_col)`** — Fits an `XGBClassifier` (200 trees, max depth 4, learning rate 0.05) on the labeled feature DataFrame.
- **`predict(df)`** — Takes the most recent row of features and returns `{"signal": 0 or 1, "probability": 0.0–1.0}`.
- **`get_feature_importance()`** — Returns features ranked by **gain** (how much each feature reduces prediction error averaged across all trees). This is the endpoint exposed at `GET /api/v1/ml/xgboost/features` — it tells you *why* the model made a decision.
- **`save(ticker)`** / **`load(ticker)`** — Persist/restore model in XGBoost's native JSON format.

---

## `hmm/` — Market Regime Detector

**Two files:**

**`model.py`** — **`RegimeDetector`**: wraps `hmmlearn.hmm.GaussianHMM` with 4 states. After fitting, it automatically assigns human-readable labels by sorting states on mean volatility (the first feature column). States are labeled: `low_volatility`, `mean_reverting`, `trending`, `high_volatility`.

Key methods:
- **`fit(features)`** — Fits the 4-state HMM using Expectation-Maximization (EM — an iterative algorithm that alternates between assigning data points to states and updating state parameters until convergence).
- **`predict(features)`** — Returns the most likely regime for each time step.
- **`predict_proba(features)`** — Returns posterior probabilities for each regime at each time step — useful for soft regime signals.
- **`regime_label(state_idx)`** — Maps a numeric state index to its human-readable name.
- **`save(path)`** / **`load(path)`** — Pickle serialization.

**`train.py`** — The training script that downloads data, computes regime features (volatility proxy, yield spread, momentum), and calls `RegimeDetector.fit()`.

---

## `transformer/` — Deferred

This directory is a placeholder. The Transformer model is planned but not yet implemented. See [`docs/adr/ADR-005-transformer-deferral.md`](../../docs/adr/ADR-005-transformer-deferral.md) for full details.

**Proposed architecture (for future implementation):**
```
Input: (batch, seq_len, n_features)
  → Linear projection → d_model=64
  → Sinusoidal positional encoding
  → 2 × TransformerEncoderLayer (4 heads, feedforward dim 128)
  → Global average pooling → d_model
  → Linear head → 3 classes (down / flat / up)
```

The Transformer would use the **same 3-class output** as the LSTM, making it directly comparable. It would be implemented using PyTorch's built-in `nn.TransformerEncoder` — no extra dependencies needed.

**Re-engagement criteria:** GPU training path available, 30+ days of tick data ingested, and LSTM/XGBoost Sharpe benchmarks documented on held-out 2024 data.

---

## Shared Feature Columns

Both LSTM and XGBoost use these 14 core features:

| Feature | Description |
|---|---|
| `open_rel`, `high_rel`, `low_rel` | Open/high/low as % of close (scale-invariant) |
| `return_1`, `return_5`, `return_10` | 1/5/10-bar percentage returns |
| `sma_10`, `sma_20`, `sma_50` | Moving averages as ratio to close |
| `rsi_14` | 14-day RSI (0-100) |
| `macd`, `macd_signal`, `macd_hist` | MACD line, signal, and histogram |
| `bb_position` | Where in the Bollinger Band the price sits (0 = at lower band, 1 = at upper) |
| `volume_ratio` | Current volume ÷ 20-day average volume |

XGBoost adds: `lag_1`, `lag_3`, `lag_5`, `lag_10` (returns at those lookback periods).

---

## How does this connect to the rest of the app?

- `backend/app/tasks/ml_tasks.py` calls into `lstm/train.py` and `xgboost/model.py` to run training as Celery jobs
- `backend/app/api/v1/ml.py` loads saved model weights and calls `predict()` for real-time inference
- The feature engineering pipeline in `lstm/dataset.py` is imported by the XGBoost model — a single shared function builds features for both models
