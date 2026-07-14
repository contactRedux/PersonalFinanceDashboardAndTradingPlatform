# backend/app/models — Database Table Definitions

## What is this folder?

This folder is the blueprint for the database. Every file here describes one or more database tables — what columns they have, what type of data goes in each column, and how tables relate to each other.

Think of it like the forms a bank uses: a "User Account Form" defines fields like name, email, and date of birth. Similarly, `user.py` here defines the `users` table with columns like `email`, `password_hash`, and `role`.

QuantNexus uses **SQLAlchemy ORM** (Object Relational Mapper — a system that lets you work with database tables as Python classes instead of writing raw SQL queries).

---

## Files

| File | Table(s) | What it stores |
|---|---|---|
| `user.py` | `users` | Login credentials (hashed), roles, 2FA secret |
| `ohlcv.py` | `ohlcv`, `ticks` | Historical price bars and individual trade prints |
| `order.py` | `orders` | Paper trades — lifecycle from `pending` to `filled` |
| `portfolio.py` | `portfolios`, `positions` | Account value and open stock holdings |
| `alert.py` | `alerts` | Price/indicator trigger conditions set by the user |
| `watchlist.py` | `watchlists` | User-saved lists of stock tickers to track |
| `workspace.py` | `workspaces`, `workspace_members` | Named dashboard layouts with team sharing |
| `strategy_config.py` | `strategy_configs` | Visual strategy builder node-graph configs (saved as JSON) |
| `dashboard_layout.py` | `dashboard_layouts` | Saved panel grid arrangements |
| `fundamental.py` | `fundamentals` | P/E ratio, market cap, earnings data per ticker |
| `economic_event.py` | `economic_events` | FOMC meetings, CPI releases, GDP announcements |
| `audit_log.py` | `audit_log` | Append-only log of all login events, trades, and config changes |

---

## Most Important Classes

**`OHLCV`** in [`ohlcv.py`](ohlcv.py) — The most-read table in the system. Stores one row per (symbol, timeframe, timestamp) combination. For example: `("AAPL", "1d", "2024-01-15")` with open=$183, high=$186, low=$182, close=$185, volume=55M. This table is a **TimescaleDB hypertable** — meaning it's automatically partitioned by time for fast range queries, like a filing cabinet with monthly folders.

**`Tick`** in [`ohlcv.py`](ohlcv.py) — Individual trade prints. Every single transaction reported by the exchange (e.g. "100 shares of AAPL traded at $185.23 at 10:32:04.872") is stored here. Partitioned in 1-hour chunks.

**`Order`** in [`order.py`](order.py) — Tracks paper trade lifecycle: `pending` → `submitted` → `partially_filled` → `filled` (or `cancelled` / `rejected`). Contains the original order details (symbol, side, quantity, price) plus fill results (filled quantity, average fill price).

**`Alert`** in [`alert.py`](alert.py) — The condition field stores a flexible JSON rule like `{"field": "price", "op": "gte", "value": 200.0}`. When the Celery task `evaluate_alerts` runs every minute, it reads all active alerts and checks this condition against the live price.

**`User`** in [`user.py`](user.py) — Stores `password_hash` (never the plain password), `totp_secret` (for two-factor authentication — like Google Authenticator), and `role` which controls what that user can do.

---

## How does this connect to the rest of the app?

- These models are imported by **`app/api/v1/`** route handlers and **`app/tasks/`** background jobs whenever they need to read from or write to the database
- The **`migrations/`** folder tracks all structural changes to these tables over time — running `make migrate` applies any pending changes safely
- The `ohlcv` and `ticks` tables use TimescaleDB's time-series optimizations; all other tables use standard PostgreSQL
- MongoDB stores news articles (not modeled here — they use a flexible document schema in `app/services/news/`)
