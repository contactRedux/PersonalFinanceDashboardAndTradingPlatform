# System Overview — QuantNexus

## Service Topology

```
Browser
  │ HTTPS
  ▼
Nginx (reverse proxy, :80)
  ├──► Next.js Frontend (:3000) — React dashboard, SSR auth pages
  └──► FastAPI Backend (:8000)
         ├──► TimescaleDB (:5432) — OHLCV, ticks, order book snapshots
         ├──► PostgreSQL (:5432) — users, orders, portfolios, strategies, workspaces
         ├──► Redis (:6379) — quote cache, pub/sub, rate limiting, Celery broker
         ├──► MongoDB (:27017) — news articles, sentiment aggregates
         └──► Celery Workers
                ├── Data refresh tasks (OHLCV, ticks)
                ├── ML training tasks (LSTM, XGBoost, HMM)
                └── Alert evaluation (every 60 seconds)

Prometheus (:9090) ← scrapes → Backend /metrics
Grafana (:3001) ← queries → Prometheus
```

> **Note:** TimescaleDB and PostgreSQL share the same port (:5432) because TimescaleDB is a
> PostgreSQL extension running in the same container. They are logically separate databases
> (`quantnexus` for application data, time-series tables in the same instance with hypertable
> partitioning) rather than separate processes.

---

## Component Responsibilities

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| **Nginx** | nginx:alpine | Request routing, SSL termination, static asset caching, upstream proxy to Next.js and FastAPI |
| **Next.js** | Next.js 15, React 19 | User interface, hybrid SSR (auth pages) / CSR (trading panels), auth guards, TradingView Lightweight Charts |
| **FastAPI** | FastAPI, Python 3.12 | REST API, WebSocket feeds, JWT authentication, rate limiting, OpenAPI documentation at `/docs` |
| **TimescaleDB** | PostgreSQL 16 + TimescaleDB extension | Time-series market data: OHLCV hypertable, ticks hypertable, automatic chunk partitioning and compression |
| **PostgreSQL** | PostgreSQL 16 | Relational application data: users, orders, portfolios, strategies, workspaces, alerts, journal entries |
| **Redis** | Redis 7 | High-speed quote cache (5-second TTL), pub/sub relay for real-time WebSocket feeds, rate-limit counters, Celery broker (db 1) and result backend (db 2) |
| **MongoDB** | MongoDB 7 | Unstructured data: news articles (RSS + NewsAPI), FinBERT sentiment scores, aggregated sentiment time-series |
| **Celery** | Celery 5, Redis broker | Async background jobs: OHLCV data refresh (every 5 minutes), ML model training (LSTM, XGBoost), alert evaluation (every 60 seconds), PDF report generation |
| **Prometheus / Grafana** | Prometheus 2, Grafana 10 | Metrics scraping from FastAPI `/metrics` endpoint (via `prometheus-fastapi-instrumentator`), dashboards for request latency, error rates, WebSocket connections, Celery queue depth |

---

## Network Boundaries

All internal service communication happens on the Docker Compose `quantnexus-network` bridge
network. Only Nginx (:80, :443) and Grafana (:3001) are exposed to the host machine. The
FastAPI backend is not directly reachable from outside Docker — all traffic arrives via Nginx.

---

## Deployment Environments

| Environment | Frontend | Backend | Databases |
|-------------|----------|---------|-----------|
| Local dev | `npm run dev` (:3000) | `uvicorn` (:8000) | Docker Compose services |
| CI | `npm run build` check | `pytest` + ruff | SQLite (tests), no Redis (mocked) |
| Production | Docker image behind Nginx | Gunicorn + Uvicorn workers | Managed PostgreSQL, Elasticache Redis |

---

## Related Documentation

- [`docs/adr/`](../adr/README.md) — Architecture Decision Records explaining each technology choice
- [`docs/architecture/data-flow.md`](data-flow.md) — Sequence diagrams for market data ingestion, backtest execution, and alert evaluation
- [`docs/architecture/api-contract.md`](api-contract.md) — Complete API route inventory
- [`docs/architecture/database-schema.md`](database-schema.md) — ORM model and database schema reference
