# PersonalFinanceDashboardAndTradingPlatform

## Machine Learning Models

| Model | Status | Endpoint | Notes |
|-------|--------|----------|-------|
| **LSTM Price Predictor** | ✅ Implemented | `POST /api/v1/ml/lstm/train`<br>`GET /api/v1/ml/lstm/predict` | 3-class return classifier (up/flat/down); PyTorch; Celery training |
| **XGBoost Signal Classifier** | ✅ Implemented | `POST /api/v1/ml/xgboost/train`<br>`GET /api/v1/ml/xgboost/predict`<br>`GET /api/v1/ml/xgboost/features` | Binary long/no-position signal; feature importance endpoint |
| **Transformer** | 🔜 Deferred | — | See [ADR-005](docs/adr/ADR-005-transformer-deferral.md) for rationale, proposed architecture, and re-engagement criteria |

Model weights are stored in the `data/ml_weights/` volume. Set `ML_WEIGHTS_DIR` env var to override the path.
