# docs/ — Documentation Index

## What is this folder?

This folder is the platform's library — written documentation for developers and architects who want to understand *why* things are built the way they are, and *how* to deploy and operate the system.

---

## Subfolders

| Folder | Contents |
|---|---|
| [`adr/`](adr/) | Architecture Decision Records — formal write-ups of major technical decisions |
| [`architecture/`](architecture/) | System design documents: database schema, data flow diagrams |
| [`developer/`](developer/) | Practical how-to guides: deployment steps, load testing |
| [`decisions/`](decisions/) | Informal decision notes and planning documents |

---

## Key Documents

### [`architecture/database-schema.md`](architecture/database-schema.md)
A complete reference for every database table and Redis key structure. Covers:
- **TimescaleDB** hypertables: `ohlcv` (price bars) and `ticks` (individual trades)
- **PostgreSQL** tables: `users`, `orders`, `alerts`, `portfolios`, `positions`, `watchlists`, `workspaces`, `strategy_configs`, `fundamentals`, `economic_events`, `audit_log`
- **MongoDB** collections: `news_articles` (with FinBERT sentiment data), `ticker_sentiment_aggregate`
- **Redis** key patterns with TTLs (how long each cached value lives before expiring)

Essential reading before writing any code that touches the database.

### [`developer/deployment.md`](developer/deployment.md)
Step-by-step instructions for:
1. Local Docker Compose development (quickest start)
2. Kubernetes deployment (`kubectl apply -f infra/k8s/`)
3. AWS ECS Fargate via Terraform (`make tf-plan && make tf-apply`)

Includes all environment variable references.

### [`developer/load-testing.md`](developer/load-testing.md)
Guide to running k6 (a load testing tool) against the platform:
- `ws_market.js` — simulates 1,000 concurrent WebSocket subscribers; threshold: p99 latency < 100ms
- `rest_auth.js` — 200 REST requests/second; threshold: p99 < 500ms
Includes CI/GitHub Actions integration example.

### [`adr/`](adr/) — Architecture Decision Records
See [`adr/README.md`](adr/README.md) for the full ADR index.

---

## How does this connect to the rest of the app?

- The ADRs in `adr/` explain decisions that shaped code in `backend/`, `ml/`, and `infra/`
- `architecture/database-schema.md` is the source of truth for the models in `backend/app/models/`
- `developer/deployment.md` references the files in `infra/k8s/` and `infra/terraform/`
- `developer/load-testing.md` references the scripts in `tests/load/`
