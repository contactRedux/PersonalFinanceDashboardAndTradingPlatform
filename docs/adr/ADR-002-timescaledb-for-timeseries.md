# ADR-002 — TimescaleDB for Time-Series Market Data

**Date:** 2025-01-10  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The platform ingests and queries large volumes of time-series data: OHLCV bars (daily, hourly,
and minute-level) for hundreds of symbols, tick-level trade data, and order book snapshots.
Three specialised storage options were evaluated: InfluxDB, ClickHouse, and TimescaleDB
(a PostgreSQL extension). Plain PostgreSQL without the extension was also considered as a
baseline.

InfluxDB is purpose-built for time-series and offers excellent write throughput (millions of
points per second) and a dedicated query language (Flux / InfluxQL). However, it introduces a
second database technology into the stack alongside PostgreSQL (which is still needed for
relational application data — users, orders, portfolios). Operating two separate databases
increases infrastructure complexity, splits the ORM layer, and eliminates the possibility of
cross-schema joins between market data and application data.

ClickHouse delivers impressive analytical query performance on hundreds of millions of rows but
is oriented toward append-only columnar analytics rather than transactional workloads. It also
requires a separate binary and has limited support for the SQLAlchemy ORM used elsewhere in the
stack.

## Decision

Use **TimescaleDB** as the time-series store for OHLCV bars and ticks.

TimescaleDB is a PostgreSQL extension that enables automatic time-based partitioning
(hypertables) without any changes to the SQL query interface. The `ohlcv` and `ticks` tables are
created as hypertables partitioned by the `time` column, enabling automatic chunk management and
significant compression. Because TimescaleDB is standard PostgreSQL under the hood, SQLAlchemy,
`asyncpg`, and all existing ORM models continue to work without modification. Continuous
aggregates and `time_bucket()` functions handle OHLCV downsampling queries at the database level
rather than in application code.

## Consequences

### Positive
- Full SQL compatibility: all existing ORM models, joins, and migration tooling (Alembic) work
  unchanged
- Automatic time-based partitioning (hypertables) eliminates manual partition management
- `time_bucket()` aggregate function enables efficient server-side OHLCV resampling
- Single database process to operate and back up (PostgreSQL + TimescaleDB extension)
- Native compression on historical chunks reduces storage by 90–95% for OHLCV data

### Negative
- Write throughput is lower than InfluxDB for pure time-series ingestion workloads; not
  suitable if tick ingest exceeds ~50,000 rows/second per node without further tuning
- TimescaleDB license changed to Timescale License (TSL) for enterprise features; the community
  edition covers all features used here but awareness of the license boundary is important
- Team must understand hypertable concepts (chunk intervals, compression policies, continuous
  aggregates) that do not exist in standard PostgreSQL

### Neutral
- TimescaleDB is installed as a Docker image extension; local development requires the
  `timescale/timescaledb` image rather than the standard `postgres` image
- Schema migrations for hypertable creation must use raw SQL (via Alembic's `op.execute()`)
  rather than pure SQLAlchemy table definitions
