# ADR-005: Defer Transformer Time-Series Model

**Status:** Accepted  
**Date:** 2026-07-15  
**Authors:** Platform Engineering Team  
**Supersedes:** None  
**Context:** ML model strategy for price prediction (alongside LSTM and XGBoost)

---

## Context

The platform audit identified three ML model targets for price prediction:

1. **LSTM** (implemented in ST-16) — sequence modelling, 3-class return classifier  
2. **XGBoost** (implemented in ST-17) — gradient-boosted binary signal classifier  
3. **Transformer** — this ADR

The LSTM and XGBoost models cover the immediate requirements:
- Short-horizon return direction prediction (LSTM)
- Actionable long/no-position signals with feature attribution (XGBoost)

A Transformer model would provide a complementary architecture with potential
advantages in longer-range dependency modelling, but requires additional investment
to match the proven production readiness of the other two models.

---

## Decision

**Defer** the Transformer model implementation to a future sprint.

The deferral is **not indefinite**: specific re-engagement criteria are defined below.

---

## Rationale

### Why Defer

1. **Diminishing marginal value at current scale.** On daily/hourly bar data with
   typical training windows of 1–2 years, LSTM and XGBoost together cover the
   signal generation use case. Transformer architectures show their largest gains
   on very long sequences (>1,000 tokens) and large datasets — conditions not yet
   met in production.

2. **Benchmarking infrastructure not in place.** A responsible Transformer deployment
   requires: (a) reproducible backtesting with statistically significant out-of-sample
   periods, (b) comparison baselines against LSTM and XGBoost on identical data splits,
   and (c) model-agnostic evaluation harness. This infrastructure exists conceptually
   but has not been built for the ML pipeline yet.

3. **Dependency footprint.** A production Transformer adds `transformers`, potentially
   `sentencepiece`, and multi-GB model artefacts. The LSTM + XGBoost footprint is already
   substantial; further growth should be justified by measured performance gains.

4. **Training compute.** Transformers typically require 5–20× the compute of an
   equivalent LSTM for time-series tasks. Until the platform has a GPU-enabled training
   path (Celery worker with CUDA), training times would be prohibitive for daily retraining.

### Why It Is Still Worth Revisiting

- Transformer-based time-series models (e.g., Temporal Fusion Transformer, PatchTST,
  Autoformer) have demonstrated strong results on financial forecasting benchmarks.
- If tick-level or intraday data is ingested at scale (ST-5 record_ticks), sequence
  lengths will grow to the regime where Transformers have clear advantages.
- The feature engineering pipeline built for LSTM/XGBoost is directly reusable.

---

## Proposed Architecture (for Re-engagement)

When the re-engagement criteria below are met, the following architecture is proposed:

### Model

**Vanilla encoder-only Transformer** (no pre-trained weights required):

```
Input: (batch, seq_len, n_features)
  └─ Linear projection → (batch, seq_len, d_model)
  └─ Positional encoding (sinusoidal)
  └─ N × TransformerEncoderLayer (d_model, nhead, dim_feedforward, dropout)
  └─ Global average pooling → (batch, d_model)
  └─ Linear head → (batch, 3)  ← same 3-class output as LSTM
Output: softmax probabilities (down, flat, up)
```

Recommended starting hyperparameters:
- `d_model = 64`, `nhead = 4`, `num_layers = 2`, `dim_feedforward = 128`
- `seq_len = 60` (daily) or `seq_len = 240` (hourly)
- `dropout = 0.1`

### Interface

The class must implement the same interface as `LSTMPricePredictor`:
- `forward(x)` → raw logits `(batch, 3)`
- `predict_proba(x)` → softmax probabilities
- Trained via `train_transformer(ticker, start, end, ...)` Celery task
- Endpoints: `POST /ml/transformer/train`, `GET /ml/transformer/predict`

### Library

Use PyTorch's built-in `nn.TransformerEncoder` / `nn.TransformerEncoderLayer`
(available since PyTorch 1.1, no additional dependencies).

---

## Re-engagement Criteria

The Transformer model should be implemented when **all** of the following are met:

| Criterion | Threshold |
|-----------|-----------|
| ML pipeline benchmarking harness in place | Reproducible OOS evaluation comparing LSTM, XGBoost, and candidate models on identical data splits |
| GPU training path available | Celery worker configured with CUDA device (or cloud training job) |
| Tick data ingested at scale | `ticks` hypertable populated with ≥30 days of continuous intraday data for ≥10 symbols |
| LSTM/XGBoost baseline measured | Sharpe ratio and accuracy benchmarks documented on held-out 2024 data |
| Team capacity | Transformer implementation, evaluation, and deployment scoped into a sprint |

---

## Consequences

### Positive
- Faster delivery of LSTM + XGBoost (both already implemented)
- Avoids premature architectural complexity
- Deferred cost is bounded by clear re-engagement criteria

### Negative
- Transformer architecture advantages not exploited in short term
- If tick data volume grows rapidly, the re-engagement backlog may lag

---

## Related ADRs

- ADR-001 through ADR-004 (see `docs/adr/`)
- ML implementation plan: `platform-completion-plan.md` ST-16, ST-17

---

## References

- Lim et al. (2021). Temporal Fusion Transformers for Interpretable Multi-Horizon Time Series Forecasting. https://arxiv.org/abs/1912.09363
- Nie et al. (2023). A Time Series is Worth 64 Words: PatchTST. https://arxiv.org/abs/2211.14730
- PyTorch `nn.TransformerEncoder` documentation: https://pytorch.org/docs/stable/generated/torch.nn.TransformerEncoder.html
