# Database Schema — QuantNexus

## Overview

Three database systems are used, each optimised for its access pattern:

| System | Purpose | Tables / Collections |
|---|---|---|
| **TimescaleDB** (PostgreSQL + extension) | Time-series market data | `ohlcv`, `ticks` |
| **PostgreSQL** | Relational application data | All other tables |
| **MongoDB** | Unstructured / variable-schema data | `news_articles`, `ticker_sentiment_aggregate` |
| **Redis** | Caching, real-time pub/sub, sessions | Keys documented below |

---

## TimescaleDB Tables

### `ohlcv` — OHLCV bars (hypertable)

Partitioned by `time` with **1-day chunks**. Primary access patterns:
- `WHERE symbol = ? AND timeframe = ? ORDER BY time DESC LIMIT 500`
- `WHERE symbol = ? AND timeframe = ? AND time BETWEEN ? AND ?`

| Column | Type | Notes |
|---|---|---|
| `time` | `TIMESTAMPTZ` PK | Bar close time (UTC) |
| `symbol` | `TEXT` PK | Ticker symbol e.g. `AAPL`, `BTC-USD` |
| `timeframe` | `TEXT` PK | `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w` |
| `exchange` | `TEXT` | Source exchange |
| `asset_class` | `TEXT` | `equity`, `crypto`, `forex`, `futures`, `options` |
| `open` | `NUMERIC(20,8)` | |
| `high` | `NUMERIC(20,8)` | |
| `low` | `NUMERIC(20,8)` | |
| `close` | `NUMERIC(20,8)` | |
| `volume` | `NUMERIC(30,8)` | |
| `vwap` | `NUMERIC(20,8)` | Optional |
| `trade_count` | `INTEGER` | Optional |
| `provider` | `TEXT` | Data source identifier |

**Continuous aggregate:** `ohlcv_daily` — auto-materialised daily OHLCV from `1m` bars. Refreshed hourly with a 1-hour lag.

### `ticks` — Individual trade prints (hypertable)

Partitioned by `time` with **1-hour chunks**.

| Column | Type | Notes |
|---|---|---|
| `time` | `TIMESTAMPTZ` PK | Trade timestamp (UTC) |
| `symbol` | `TEXT` PK | |
| `price` | `NUMERIC(20,8)` | |
| `size` | `NUMERIC(20,8)` | Trade size in units |
| `side` | `CHAR(1)` | `B`=buy, `S`=sell, `U`=unknown |
| `exchange` | `TEXT` | |
| `provider` | `TEXT` | |

---

## PostgreSQL Tables

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `email` | `TEXT` UNIQUE | |
| `password_hash` | `TEXT` | bcrypt hash |
| `totp_secret` | `TEXT` | Base32 TOTP secret (nullable — enabled when set) |
| `role` | `TEXT` | `admin`, `trader`, `analyst`, `readonly` |
| `is_active` | `BOOLEAN` | |

### `watchlists`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` | CASCADE delete |
| `name` | `TEXT` | |
| `symbols` | `TEXT[]` | PostgreSQL array of ticker symbols |
| `is_default` | `BOOLEAN` | One default per user |

### `alerts`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → `users.id` | |
| `symbol` | `TEXT` | |
| `alert_type` | `TEXT` | `price`, `indicator`, `news_keyword`, `pnl` |
| `condition` | `JSONB` | `{"field": "price", "op": "gte", "value": 150.0}` |
| `message` | `TEXT` | |
| `is_active` | `BOOLEAN` | |
| `triggered_at` | `TIMESTAMPTZ` | Set when alert fires |

### `portfolios`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK | |
| `name` | `TEXT` | |
| `initial_capital` | `NUMERIC(20,2)` | |
| `currency` | `TEXT` | Default `USD` |

### `positions`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `portfolio_id` | `UUID` FK → `portfolios.id` | |
| `symbol` | `TEXT` | |
| `asset_class` | `TEXT` | |
| `side` | `TEXT` | `long` or `short` |
| `quantity` | `NUMERIC(20,8)` | |
| `avg_entry_price` | `NUMERIC(20,8)` | |
| `stop_loss` | `NUMERIC(20,8)` | Optional |
| `take_profit` | `NUMERIC(20,8)` | Optional |
| `opened_at` | `TIMESTAMPTZ` | |
| `closed_at` | `TIMESTAMPTZ` | `NULL` = open position |
| `is_open` | `BOOLEAN` | |

### `fundamentals`

Refreshed daily from external data providers.

| Column | Type | Notes |
|---|---|---|
| `symbol` | `TEXT` PK | |
| `as_of_date` | `DATE` PK | |
| `market_cap` | `NUMERIC` | |
| `pe_ratio` | `NUMERIC` | |
| `pb_ratio` | `NUMERIC` | |
| `ev_ebitda` | `NUMERIC` | |
| `revenue_ttm` | `NUMERIC` | Trailing 12 months |
| `net_income_ttm` | `NUMERIC` | |
| `gross_margin` | `NUMERIC` | Ratio (0–1) |
| `debt_equity` | `NUMERIC` | |
| `dividend_yield` | `NUMERIC` | Ratio (0–1) |
| `beta` | `NUMERIC` | Market beta |
| `sector` | `TEXT` | |
| `industry` | `TEXT` | |

### `economic_events`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `event_time` | `TIMESTAMPTZ` | Indexed for range queries |
| `country` | `TEXT` | ISO 2-char code |
| `event_name` | `TEXT` | e.g. `FOMC Rate Decision` |
| `impact` | `TEXT` | `high`, `medium`, `low` |
| `forecast` | `TEXT` | Expected value (nullable) |
| `previous` | `TEXT` | Prior release value |
| `actual` | `TEXT` | Actual released value (null pre-release) |
| `currency` | `TEXT` | Affected currency |

### `dashboard_layouts`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK | |
| `name` | `TEXT` | Layout name |
| `layout` | `JSONB` | React Grid Layout serialized config |
| `is_default` | `BOOLEAN` | |

### `audit_log`

Append-only. All auth events, trade mutations, and config changes.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGINT` PK | Auto-increment sequence |
| `user_id` | `UUID` FK | Nullable (system events) |
| `action` | `TEXT` | e.g. `auth.login`, `position.create` |
| `resource` | `TEXT` | e.g. `users/uuid`, `positions/uuid` |
| `details` | `JSONB` | Action-specific payload (no secrets) |
| `ip_address` | `INET` | Client IP |
| `created_at` | `TIMESTAMPTZ` | Indexed |

---

## Redis Key Structures

All keys use the prefix pattern `{namespace}:{identifier}`.

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| `quote:{SYMBOL}` | Hash | 60s | Latest quote fields (price, bid, ask, volume, change_pct) |
| `sentiment:{SYMBOL}` | String (JSON) | 300s | Aggregate sentiment payload |
| `session:{token_jti}` | String (JSON) | 7d | Refresh token store (single-use rotation) |
| `refresh_token:{token}` | Hash | 7d | Refresh token payload (sub, email, role) |
| `ratelimit:{user_id}:{endpoint}` | String (counter) | variable | Per-user rate limit counter |
| `bar:{SYMBOL}:{TIMEFRAME}:latest` | Hash | 60s | Latest OHLCV bar for quick chart updates |
| `screener:{filter_hash}` | String (JSON) | 60s | Screener result cache |
| `channel:quotes` | Pub/Sub | — | All quote updates (global broadcast) |
| `channel:quotes:{SYMBOL}` | Pub/Sub | — | Per-symbol quote updates |
| `channel:tape` | Pub/Sub | — | All time & sales prints |
| `channel:tape:{SYMBOL}` | Pub/Sub | — | Per-symbol tape |
| `channel:orderbook:{SYMBOL}` | Pub/Sub | — | Level 2 order book snapshots |
| `channel:alerts:{USER_ID}` | Pub/Sub | — | Per-user triggered alert notifications |

---

## MongoDB Collections

### `news_articles`

```json
{
  "_id": "ObjectId",
  "source": "benzinga | newsapi | seeking_alpha | reddit | sec_edgar | twitter",
  "source_id": "string — provider-side article ID",
  "headline": "string",
  "body": "string (optional — full text if available)",
  "url": "string",
  "published_at": "ISODate",
  "tickers_mentioned": ["AAPL", "MSFT"],
  "sentiment": {
    "finbert_score": -1.0,
    "finbert_confidence": 0.95,
    "openai_score": -0.8,
    "openai_confidence": 0.92,
    "composite_score": -0.91,
    "label": "bullish | bearish | neutral",
    "impact_category": "earnings | macro | regulatory | ma | analyst | general"
  },
  "processed_at": "ISODate"
}
```

**Indexes:**
- `(source, source_id)` — unique, prevents duplicate ingestion
- `tickers_mentioned` — most common query filter
- `published_at DESC` — feed pagination
- `(sentiment.label, published_at DESC)` — filtered sentiment queries
- `sentiment.impact_category` — impact-gated GPT-4o scoring

### `ticker_sentiment_aggregate`

```json
{
  "_id": "ObjectId",
  "symbol": "AAPL",
  "updated_at": "ISODate",
  "score_1h": -0.23,
  "score_4h": -0.15,
  "score_1d": -0.08,
  "article_count_1h": 3,
  "article_count_1d": 12,
  "dominant_label": "bearish",
  "top_articles": ["ObjectId", "ObjectId", "ObjectId"]
}
```

**Indexes:**
- `symbol` — unique, primary lookup
- `updated_at DESC` — freshness checks

---

## Running Migrations

```bash
# Generate a new migration (autogenerate from ORM models)
make migrate-generate MSG="description_of_change"

# Apply all pending migrations
make migrate

# Roll back one migration
make migrate-down

# TimescaleDB post-migration setup (requires live TimescaleDB)
psql $DATABASE_URL -f infra/docker/setup-timescaledb.sql

# MongoDB index initialization
cd backend && uv run python -m scripts.init_mongodb_indexes
```
