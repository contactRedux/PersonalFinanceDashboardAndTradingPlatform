# ADR-002: Database Selection — TimescaleDB + PostgreSQL + Redis + MongoDB

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2025-01-15 |
| **Deciders** | Platform team |
| **Supersedes** | — |

---

## Context

QuantNexus stores and queries four fundamentally different kinds of data:

| Data kind | Access pattern | Volume |
|---|---|---|
| OHLCV tick / candle data | Time-range scans; continuous aggregates | High — millions of rows/day |
| User, portfolio, order records | Relational joins; ACID transactions | Medium |
| Real-time quote + orderbook state | Sub-millisecond pub/sub; ephemeral cache | Very high throughput |
| AI analysis, news, strategy docs | Schema-free documents; full-text search | Variable |

No single database technology serves all four patterns optimally.

### Alternatives evaluated

| Technology | Time-series | Relational | Pub/Sub cache | Documents |
|---|---|---|---|---|
| **PostgreSQL only** | Partial (no hypertables) | ✓ | ✗ | ✗ |
| **InfluxDB + PostgreSQL** | ✓ | ✓ | ✗ | ✗ |
| **DynamoDB** | ✗ | ✗ | ✗ | ✓ (single-table) |
| **TimescaleDB + PG + Redis + MongoDB** | ✓ | ✓ | ✓ | ✓ |

---

## Decision

Adopt a **quad-store architecture**:

| Store | Role |
|---|---|
| **TimescaleDB** | OHLCV candles + tick data as hypertables; continuous aggregates for VWAP/EMA |
| **PostgreSQL** | Users, portfolios, orders, watchlists; ACID-compliant relational data |
| **Redis** | Real-time quote cache (sub-ms reads); WebSocket fan-out pub/sub channel |
| **MongoDB** | AI analysis results, news documents, strategy configuration blobs |

TimescaleDB runs as a PostgreSQL extension, so both share the same Postgres
process in development; in production they run in separate instances to allow
independent scaling.

---

## Consequences

### Positive

- **TimescaleDB hypertables** compress OHLCV data automatically and provide
  `time_bucket` + continuous aggregate queries that are orders of magnitude
  faster than naive Postgres timestamp indexes at scale.
- **PostgreSQL** handles complex joins for portfolio P&L calculations,
  order history aggregation, and user permission checks with full ACID
  guarantees.
- **Redis pub/sub** delivers real-time price updates to WebSocket handlers in
  under 1 ms, avoiding polling loops and database load.
- **MongoDB** stores schema-flexible documents (LLM analysis output, news
  articles with arbitrary metadata) without requiring migration scripts
  for every new field.

### Negative / trade-offs

- **Operational complexity** — four data stores require monitoring, backup,
  and runbook coverage for each. On-call engineers must be familiar with
  all four.
- **Data consistency across stores** — updates that span stores (e.g., an
  order fill that must update PostgreSQL orders + Redis cache + MongoDB
  strategy stats) require application-level coordination; there is no
  distributed transaction.
- **Local dev dependencies** — `docker compose` must spin up four services;
  cold-start time increases.

### Mitigations

- A thin `DataAccessLayer` abstraction in the backend routes each query type
  to the correct store; business logic never calls raw clients directly.
- Redis is treated as a **write-through cache**: PostgreSQL is always the
  source of truth for persisted state; Redis keys have short TTLs and are
  rebuilt on cache miss.
- MongoDB documents that require cross-store consistency carry a `pg_order_id`
  foreign-key field so reconciliation queries are possible.
