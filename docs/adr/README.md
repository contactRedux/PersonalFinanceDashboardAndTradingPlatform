# docs/adr — Architecture Decision Records

## What is this folder?

An **ADR** (Architecture Decision Record) is a short document that captures an important technical decision: what was decided, why that choice was made over alternatives, and what the consequences are.

Think of ADRs like meeting minutes for engineering decisions. When you come back to the codebase months later and wonder "why did we do it this way?" — the ADR has the answer, written at the time the decision was fresh.

Each ADR follows the same format:
- **Status** (Proposed / Accepted / Superseded)
- **Context** — What problem were we trying to solve?
- **Decision** — What did we choose?
- **Consequences** — What trade-offs did we accept?

---

## ADR Index

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-001](ADR-001-fastapi-sqlalchemy.md) | FastAPI + SQLAlchemy Async for the Backend API | ✅ Accepted | 2025-01-10 |
| [ADR-002](ADR-002-timescaledb-for-timeseries.md) | TimescaleDB for Time-Series Market Data | ✅ Accepted | 2025-01-10 |
| [ADR-003](ADR-003-nextjs-lightweight-charts.md) | Next.js 15 + TradingView Lightweight Charts | ✅ Accepted | 2025-01-10 |
| [ADR-004](ADR-004-celery-redis-worker.md) | Celery + Redis for Background Task Execution | ✅ Accepted | 2025-01-10 |
| [ADR-005](ADR-005-transformer-deferral.md) | Defer Transformer Time-Series Model | ✅ Accepted | 2026-07-15 |
| [ADR-006](ADR-006-db-backed-strategies.md) | Database-Backed Strategy Configurations | ✅ Accepted | 2025-02-14 |
| [ADR-007](ADR-007-weasyprint-pdf-reports.md) | WeasyPrint for PDF Backtest Report Generation | ✅ Accepted | 2025-03-01 |
| [ADR-008](ADR-008-pytorch-lstm-model.md) | PyTorch for LSTM Price Prediction Model | ✅ Accepted | 2025-03-15 |

---

## Quick Reference

| ADR | One-Line Summary |
|-----|-----------------|
| ADR-001 | FastAPI + SQLAlchemy async chosen over Django and Flask for native async I/O and auto-generated OpenAPI docs |
| ADR-002 | TimescaleDB chosen over InfluxDB and ClickHouse for SQL compatibility and automatic hypertable partitioning |
| ADR-003 | Next.js 15 App Router + Lightweight Charts chosen for hybrid SSR/CSR rendering and 60 fps chart performance |
| ADR-004 | Celery + Redis chosen for async background jobs; Redis already in stack, no new infrastructure dependency |
| ADR-005 | Transformer model deferred until GPU training path and tick data volume justify the compute cost |
| ADR-006 | Strategy configs moved from in-memory dict to PostgreSQL `StrategyConfig` model for persistence and multi-user isolation |
| ADR-007 | WeasyPrint chosen over ReportLab for PDF reports; reuses existing HTML template directly |
| ADR-008 | PyTorch chosen over TensorFlow/Keras for LSTM; Pythonic API, research ecosystem, and TransformerEncoder already available |

---

## How to Write a New ADR

1. Copy an existing ADR file as a template
2. Name it `ADR-NNN-short-title.md` (where NNN is the next available number)
3. Fill in all sections honestly — especially the **Consequences** section (both positive and negative)
4. Add it to the index table above with Number, Title, Status, and Date
5. Link to it from the relevant code with a comment: `# See ADR-NNN`

---

## How does this connect to the rest of the app?

- ADR-001 explains the FastAPI + async SQLAlchemy architecture throughout `backend/app/`
- ADR-002 explains the `timescale/timescaledb` Docker image and hypertable migrations in `backend/alembic/versions/`
- ADR-003 explains the Next.js App Router structure under `frontend/app/` and the use of `lightweight-charts` in `ChartCanvas.tsx`
- ADR-004 explains the `celery_worker` and `celery_beat` Docker Compose services and tasks under `backend/app/tasks/`
- ADR-005 directly explains the empty `ml/models/transformer/` directory
- ADR-006 explains the `StrategyConfig` ORM model in `backend/app/models/strategy_config.py`
- ADR-007 explains the `generate_pdf_report()` function in `backtesting/reporting/pdf_report.py`
- ADR-008 explains the PyTorch dependency and `.pt` weight files under `/app/data/ml_weights/lstm/`
