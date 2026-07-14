# ADR-006 — Database-Backed Strategy Configurations

**Date:** 2025-02-14  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The initial prototype stored user-defined strategy configurations (strategy name, parameters,
associated symbol, timeframe, and user ownership) in a process-level Python dictionary keyed by
a UUID. This approach was sufficient for single-session development testing but had three
critical failure modes: strategy configurations were lost on every API server restart, the
in-memory store was not shared between multiple API worker processes (making horizontal scaling
impossible), and there was no user-level isolation — any authenticated user could enumerate all
strategy IDs.

The platform's stated requirement is that users can build, save, and iterate on strategy
configurations across multiple sessions and devices. A persistent, per-user strategy store is
therefore a hard requirement, not a nice-to-have. Three storage options were considered for the
per-user strategy configuration store: the existing PostgreSQL database (via a new ORM model), a
Redis hash store (keyed by user ID), and a document store (MongoDB, already in the stack for
news articles). Redis does not support ad-hoc SQL queries or foreign-key relationships; MongoDB
would introduce schema-less documents for what is essentially a structured, relational record.

## Decision

Add a **`StrategyConfig` ORM model backed by PostgreSQL** and replace the in-memory dict with
database reads and writes throughout the `/api/v1/strategies` router.

The `StrategyConfig` model (`backend/app/models/strategy_config.py`) holds `id`, `user_id`
(foreign key to `users`), `name`, `strategy_type`, `params` (JSONB column), `symbol`,
`timeframe`, and `created_at`. All CRUD operations in the strategies router use an
`AsyncSession` query against this table, scoped to `current_user["sub"]` so that each user sees
only their own strategies. A new Alembic migration creates the table on upgrade.

## Consequences

### Positive
- Strategy configurations persist across API server restarts and redeployments
- Multi-user isolation is enforced at the database query level (`WHERE user_id = :uid`)
- JSONB `params` column allows flexible strategy parameters without requiring a schema migration
  per new strategy type
- Full SQL queryability: future features (strategy analytics, aggregations across users for
  admin dashboards) are straightforward to implement

### Negative
- Requires a database migration (`alembic upgrade head`) on first deployment after this change;
  existing deployments without the migration will see a 500 error on strategy endpoints
- Every strategy read and write now incurs a database round-trip; the in-memory dict was
  effectively O(1) with no I/O latency (acceptable trade-off given the persistence requirement)

### Neutral
- The `params` column stores arbitrary JSON, so strategy parameter validation is the
  responsibility of the API layer (Pydantic schema), not the database schema
- The migration is idempotent: running `alembic upgrade head` multiple times is safe
