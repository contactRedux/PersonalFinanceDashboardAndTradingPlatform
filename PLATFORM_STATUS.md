# QuantNexus — Platform Status, Architecture & Roadmap

> **Living document** — supersedes the original `trading-platform-plan.md`.
> Reflects the actual production state of the codebase as of the latest session.
> All 11 original sub-tasks are complete. Three additional phases of recommended work are also complete.

---

## Table of Contents

1. [Platform Identity](#1-platform-identity)
2. [What Is Built — Complete Inventory](#2-what-is-built--complete-inventory)
3. [Technology Stack — Actual Pinned Versions](#3-technology-stack--actual-pinned-versions)
4. [Monorepo Structure — As-Built](#4-monorepo-structure--as-built)
5. [Database Schema](#5-database-schema)
6. [Full API Contract](#6-full-api-contract)
7. [Architecture Invariants](#7-architecture-invariants)
8. [Known Quirks & Suppressions](#8-known-quirks--suppressions)
9. [Validation State](#9-validation-state)
10. [Development Workflow](#10-development-workflow)
11. [Environment Variables Reference](#11-environment-variables-reference)
12. [Phased Roadmap — Original + Completed Additions](#12-phased-roadmap--original--completed-additions)
13. [Outstanding Work — What Still Needs to Be Added](#13-outstanding-work--what-still-needs-to-be-added)
14. [New Ideas for Future Phases](#14-new-ideas-for-future-phases)
15. [Architecture Diagrams](#15-architecture-diagrams)
16. [Risk Register](#16-risk-register)
17. [Regulatory Notes](#17-regulatory-notes)
18. [Compute & Cost Estimates](#18-compute--cost-estimates)

---

## 1. Platform Identity

| Field | Value |
|---|---|
| **Name** | QuantNexus |
| **Type** | Enterprise algorithmic trading dashboard — Bloomberg Terminal–inspired |
| **Target user** | Single developer / small quant team (current); multi-user cloud (future) |
| **Repo layout** | Monorepo |
| **Frontend** | Next.js 16.2.10 (App Router) + React 19.2.4 |
| **Backend** | FastAPI + Python 3.12 |
| **Package manager (Python)** | `uv` at `/Users/henrynguyen/.local/bin/uv` |
| **Node** | 22 (CI), `npm ci` for installs |

---

## 2. What Is Built — Complete Inventory

### 2.1 Original 11 Sub-Tasks — All Complete

| Sub-Task | Status | Key deliverable |
|---|---|---|
| ST-1 — Monorepo scaffold + CI | ✅ | Next.js + FastAPI + Docker Compose + GitHub Actions |
| ST-2 — Database schema init | ✅ | TimescaleDB hypertables, PostgreSQL relational schema, Redis key structure, MongoDB collections |
| ST-3 — Authentication system | ✅ | JWT + refresh rotation + TOTP 2FA + RBAC; audit log on all auth events |
| ST-4 — Design system + dashboard shell | ✅ | Tailwind v4 terminal theme; react-grid-layout v2.2.3 draggable grid |
| ST-5 — Market data layer + WebSocket | ✅ | Provider abstraction (Alpaca + yfinance); Redis pub/sub WS fan-out |
| ST-6 — Candlestick chart panel | ✅ | lightweight-charts v5.2.0; 7 timeframes; Heikin-Ashi, bar, line, area, baseline |
| ST-7 — Watchlist + Ticker Tape | ✅ | Real-time quotes; symbol search; multi-watchlist; animated price flashes |
| ST-8 — News feed + sentiment | ✅ | FinBERT + GPT-4o pipeline; Celery workers; MongoDB storage; per-ticker aggregate |
| ST-9 — Portfolio, Options, Order Book, Risk | ✅ | All four panels; Black-Scholes Greeks; VaR/CVaR/Sharpe/Sortino; Kelly Criterion |
| ST-10 — Screener, Alerts, Macro, Heat Maps, Crypto | ✅ | All 8 panels; FRED API; D3.js treemap + correlation matrix; unusual options activity |
| ST-11 — Hardening, security audit, CI | ✅ | ruff + bandit + eslint security plugin; rate limiter; audit log; Prometheus + Grafana |

### 2.2 Additional Work Completed After ST-11

| Phase | Status | Key deliverable |
|---|---|---|
| **Backtesting Engine** | ✅ | Vectorized + event-driven engines; walk-forward optimizer; Monte Carlo; HTML report; SMA cross strategy; 33 tests |
| **Order Management** | ✅ | Alpaca paper trading REST + WS; Order model; OrderEntryPanel; 10 unit tests |
| **Performance Analytics Panel** | ✅ | Win-rate gauge; P&L calendar heatmap (SVG); stat grid; trade log tab |
| **Multi-Timeframe Panel** | ✅ | 2×2 lightweight-charts v5 grid (1m/5m/1h/1d); per-pane independent fetch |
| **Playwright E2E Tests** | ✅ | 4 spec files; auth-flow runs in CI; dashboard/watchlist/chart skip without credentials |
| **CI live-data integration** | ✅ | `e2e` job (auth-flow); `live-data` job (conditional on ALPACA_SECRET_KEY) |
| **Vitest setup file** | ✅ | `tests/setup.ts`; `matchMedia` / `ResizeObserver` stubs; E2E excluded from vitest glob |

### 2.3 Dashboard Panels — All 19 Registered

| Panel | File | Data source |
|---|---|---|
| ChartPanel | `components/panels/ChartPanel/` | REST `/market/bars`; WS quotes |
| WatchlistPanel | `components/panels/WatchlistPanel/` | WS quotes; REST search |
| PortfolioPanel | `components/panels/PortfolioPanel/` | REST `/portfolio` |
| RiskPanel | `components/panels/RiskPanel/` | REST `/portfolio/risk` |
| OrderBookPanel | `components/panels/OrderBookPanel/` | WS `/ws/orderbook/{symbol}` |
| TimeAndSalesPanel | `components/panels/TimeAndSalesPanel/` | WS `/ws/tape` |
| OptionsChainPanel | `components/panels/OptionsChainPanel/` | REST `/options/chain` |
| NewsFeedPanel | `components/panels/NewsFeedPanel/` | REST `/news/feed` + `/news/sentiment` |
| ScreenerPanel | `components/panels/ScreenerPanel/` | REST `/screener/run` |
| AlertsPanel | `components/panels/AlertsPanel/` | REST `/alerts`; WS `/ws/alerts` |
| MacroPanel | `components/panels/MacroPanel/` | REST `/macro/indicators` + `/macro/yield-curve` |
| EconomicCalendarPanel | `components/panels/EconomicCalendarPanel/` | REST `/calendar/events` |
| HeatMapPanel | `components/panels/HeatMapPanel/` | REST `/screener/sector-map` |
| CorrelationMatrixPanel | `components/panels/CorrelationMatrixPanel/` | REST `/screener/correlations` |
| DarkPoolPanel | `components/panels/DarkPoolPanel/` | REST `/options/unusual-activity` |
| CryptoPanel | `components/panels/CryptoPanel/` | REST `/crypto/*` |
| **PerformancePanel** ★ | `components/panels/PerformancePanel/` | REST `/portfolio/trades`; demo fallback |
| **MultiTimeframePanel** ★ | `components/panels/MultiTimeframePanel/` | REST `/market/bars` ×4 panes |
| **OrderEntryPanel** ★ | `components/panels/OrderEntryPanel/` | REST `/orders`; WS `/ws/orders` |

★ Added after ST-11.

---

## 3. Technology Stack — Actual Pinned Versions

> **Critical:** These versions are pinned because APIs changed between major versions.
> Do not bump without reading the changelog and running the full test suite.

### Frontend (pinned)

| Library | Version | Why pinned |
|---|---|---|
| `next` | 16.2.10 | App Router API; matches `eslint-config-next` |
| `react` | 19.2.4 | Concurrent rendering; `act()` API used in tests |
| `react-grid-layout` | 2.2.3 | **New API**: `useContainerWidth()`, `gridConfig/dragConfig/resizeConfig`. Do not downgrade — pre-2.0 uses completely different prop names. |
| `lightweight-charts` | 5.2.0 | **New API**: `chart.addSeries(CandlestickSeries, opts)`. The old `addCandlestickSeries()` is removed. |
| `zustand` | 5.0.14 | Store API changed in v5 |
| `framer-motion` | 12.42.2 | — |
| `vitest` | 4.1.10 | — |

### Backend (pinned)

| Library | Version | Why pinned |
|---|---|---|
| Python | 3.12 | Async improvements; type system |
| `prometheus-fastapi-instrumentator` | 8.0.2 | Added ST-11; `should_respect_env_var` param |
| `prometheus-client` | 0.25.0 | Matches instrumentator |
| `fastapi` | ≥0.139.0 | — |
| `sqlalchemy` | ≥2.0.51 | Async ORM; v2 API |
| `numpy` | ≥2.5.1 | — |
| `pandas` | ≥3.0.3 | — |

---

## 4. Monorepo Structure — As-Built

```
/
├── .env.example                       # All env vars documented; copy → .env
├── .gitignore
├── docker-compose.yml                 # 9 services: db, redis, mongo, backend, celery,
│                                      #   frontend, nginx, prometheus, grafana
├── docker-compose.override.yml        # Dev-only overrides
├── Makefile                           # make dev|test|lint|build|migrate
├── README.md
├── trading-platform-plan.md          # Original plan (superseded by this file)
├── PLATFORM_STATUS.md                # ← This file
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # Root → /dashboard redirect
│   │   ├── globals.css                # Tailwind v4 base + terminal design tokens
│   │   ├── (auth)/
│   │   │   ├── layout.tsx
│   │   │   └── login/page.tsx
│   │   └── (dashboard)/
│   │       ├── layout.tsx             # Sidebar + Header + TickerTape shell
│   │       ├── dashboard/page.tsx     # 19-panel react-grid-layout grid
│   │       ├── charts/                # Full-screen chart route
│   │       ├── screener/              # Screener route
│   │       └── settings/              # Settings route
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Panel.tsx              # Base panel shell (drag handle, content scroll)
│   │   │   ├── PanelGrid.tsx          # react-grid-layout v2.2.3 wrapper
│   │   │   ├── Sidebar.tsx
│   │   │   └── TickerTape.tsx
│   │   ├── panels/                    # 19 panel directories (index.tsx each)
│   │   │   ├── AlertsPanel/
│   │   │   ├── ChartPanel/            # + ChartCanvas.tsx, ChartToolbar.tsx
│   │   │   ├── CorrelationMatrixPanel/
│   │   │   ├── CryptoPanel/
│   │   │   ├── DarkPoolPanel/
│   │   │   ├── EconomicCalendarPanel/
│   │   │   ├── HeatMapPanel/
│   │   │   ├── MacroPanel/
│   │   │   ├── MultiTimeframePanel/   # ★ new
│   │   │   ├── NewsFeedPanel/
│   │   │   ├── OptionsChainPanel/
│   │   │   ├── OrderBookPanel/
│   │   │   ├── OrderEntryPanel/       # ★ new
│   │   │   ├── PerformancePanel/      # ★ new
│   │   │   ├── PortfolioPanel/
│   │   │   ├── RiskPanel/
│   │   │   ├── ScreenerPanel/
│   │   │   ├── TimeAndSalesPanel/
│   │   │   └── WatchlistPanel/
│   │   ├── providers/
│   │   │   └── MarketDataProvider.tsx # Single WS connection; Zustand distribution
│   │   └── ui/                        # Radix-based shadcn/ui primitives
│   │
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useMarketData.ts
│   │   └── useWebSocket.ts
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── auth.ts
│   │   │   ├── client.ts              # Base fetch wrapper with JWT headers
│   │   │   ├── market.ts
│   │   │   ├── options.ts
│   │   │   ├── portfolio.ts
│   │   │   ├── screener.ts
│   │   │   └── websocket.ts           # WS URL builders
│   │   ├── formatters.ts              # Currency, %, volume formatters
│   │   └── indicators/
│   │       └── index.ts               # SMA, EMA, WMA, DEMA, TEMA, HMA, MACD, RSI,
│   │                                  #   Bollinger Bands, ATR, VWAP, OBV, Heikin-Ashi
│   │
│   ├── store/
│   │   ├── authStore.ts
│   │   ├── chartStore.ts              # Per-panel: symbol, timeframe, indicators (persisted)
│   │   ├── layoutStore.ts             # RGL layout (persisted); 19-panel DEFAULT_LAYOUT
│   │   ├── marketDataStore.ts         # Real-time quote map
│   │   └── watchlistStore.ts
│   │
│   ├── types/
│   │   ├── api.ts
│   │   ├── market.ts
│   │   ├── news.ts
│   │   └── portfolio.ts
│   │
│   ├── middleware.ts                  # Next.js edge auth guard
│   ├── vitest.config.ts               # include: tests/unit/**; setup: tests/setup.ts
│   ├── playwright.config.ts           # E2E config; webServer auto-starts Next.js
│   ├── eslint.config.mjs              # Flat config; eslint-plugin-security active
│   └── tests/
│       ├── setup.ts                   # matchMedia / ResizeObserver stubs
│       ├── unit/
│       │   ├── formatters.test.ts     # 12 tests
│       │   ├── indicators.test.ts     # 18 tests
│       │   ├── panels_st9.test.tsx    # 21 tests
│       │   ├── panels_st10.test.tsx   # 49 tests
│       │   └── panels_new.test.tsx    # 20 tests (Perf + MTF + OrderEntry panels)
│       └── e2e/
│           ├── auth.spec.ts           # 4 tests — runs in CI (no credentials needed)
│           ├── dashboard.spec.ts      # 2 tests — skipped without TEST_USER_EMAIL
│           ├── watchlist.spec.ts      # 2 tests — skipped without credentials
│           └── chart.spec.ts          # 2 tests — skipped without credentials
│
├── backend/
│   ├── pyproject.toml                 # uv project; ruff + bandit + pytest config
│   ├── uv.lock
│   ├── alembic.ini
│   ├── main.py                        # Entrypoint: uvicorn app.main:app
│   ├── app/
│   │   ├── main.py                    # FastAPI factory; CORS; rate limit middleware;
│   │   │                              #   error handlers; Prometheus instrumentation
│   │   ├── config.py                  # Pydantic Settings (all from env vars)
│   │   ├── database.py                # SQLAlchemy async engine + session
│   │   ├── dependencies.py            # CurrentUser, DBSession, get_redis — injected everywhere
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── router.py          # Aggregates all REST routers
│   │   │   │   ├── alerts.py
│   │   │   │   ├── auth.py            # Login + TOTP; audit log wired in
│   │   │   │   ├── backtest.py        # ★ POST /backtest/run, /backtest/wfo
│   │   │   │   ├── calendar.py
│   │   │   │   ├── crypto.py
│   │   │   │   ├── macro.py
│   │   │   │   ├── market.py
│   │   │   │   ├── news.py
│   │   │   │   ├── options.py
│   │   │   │   ├── orders.py          # ★ POST/GET/DELETE /orders
│   │   │   │   ├── portfolio.py
│   │   │   │   ├── screener.py
│   │   │   │   └── watchlist.py
│   │   │   └── ws/
│   │   │       ├── router.py          # Aggregates all WS endpoints incl. /ws/orders
│   │   │       ├── alerts_feed.py
│   │   │       ├── market_feed.py
│   │   │       ├── orderbook_feed.py
│   │   │       ├── orders_feed.py     # ★ Redis pub/sub → WS order status updates
│   │   │       └── tape_feed.py
│   │   ├── auth/
│   │   │   ├── jwt.py                 # Access + refresh token; family rotation
│   │   │   ├── password.py            # bcrypt direct (passlib compatibility bug)
│   │   │   ├── rbac.py
│   │   │   └── totp.py
│   │   ├── data/
│   │   │   ├── cache/
│   │   │   │   ├── pubsub.py
│   │   │   │   ├── quote_cache.py
│   │   │   │   └── redis_client.py
│   │   │   └── ingestion/
│   │   │       ├── normalizer.py
│   │   │       ├── scheduler.py       # APScheduler periodic refresh jobs
│   │   │       └── writer.py
│   │   ├── middleware/
│   │   │   └── rate_limit.py          # Redis sliding window: auth 10/60s, API 120/60s
│   │   ├── models/
│   │   │   ├── alert.py
│   │   │   ├── audit_log.py
│   │   │   ├── dashboard_layout.py
│   │   │   ├── economic_event.py
│   │   │   ├── fundamental.py
│   │   │   ├── ohlcv.py
│   │   │   ├── order.py               # ★ Order lifecycle model
│   │   │   ├── portfolio.py
│   │   │   ├── user.py
│   │   │   └── watchlist.py
│   │   ├── services/
│   │   │   ├── alerts/                # evaluator.py, dispatcher.py
│   │   │   ├── audit/                 # logger.py — write_audit_log() async helper
│   │   │   ├── macro/                 # fred.py — FRED API client
│   │   │   ├── market_data/           # base.py, alpaca.py, yahoo_finance.py, router.py
│   │   │   ├── news/                  # newsapi.py, benzinga.py, aggregator.py
│   │   │   ├── options/               # greeks.py — Black-Scholes + IV (Newton-Raphson)
│   │   │   ├── orders/                # ★ service.py — Alpaca paper + simulation fallback
│   │   │   ├── risk/                  # ratios.py — VaR, CVaR, Sharpe, Sortino, Calmar, Beta, Kelly
│   │   │   ├── screener/              # engine.py, universe.py
│   │   │   └── sentiment/             # finbert.py, openai_scorer.py, ner_extractor.py, aggregator.py
│   │   └── tasks/
│   │       ├── alert_tasks.py
│   │       ├── celery_app.py
│   │       ├── data_tasks.py
│   │       └── sentiment_tasks.py
│   ├── migrations/                    # Alembic revisions
│   └── tests/
│       ├── conftest.py
│       ├── integration/
│       │   ├── test_api.py            # 3 tests (health, auth validation, auth guard)
│       │   └── test_migrations.py     # 2 tests — skipped without real PostgreSQL
│       └── unit/
│           ├── test_auth.py           # 9 tests — JWT, bcrypt, TOTP, RBAC
│           ├── test_orders.py         # ★ 10 tests — OrderRequest + simulation mode
│           └── test_risk_and_greeks.py # 23 tests — VaR, Sharpe, Greeks, IV
│
├── backtesting/                       # ★ Fully implemented
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── base.py                    # BacktestResult, Trade dataclasses; Strategy protocol
│   │   ├── vectorized.py              # NumPy one-pass engine
│   │   └── event_driven.py            # Bar-by-bar event queue; MarketEvent→Signal→Order→Fill
│   ├── optimization/
│   │   ├── monte_carlo.py             # Bootstrap P&L resampler; p05–p95 percentiles
│   │   └── walk_forward.py            # Anchored IS/OOS; grid search; fold aggregation
│   ├── reporting/
│   │   └── html_report.py             # Self-contained HTML; SVG equity curve; trade log
│   ├── strategies/
│   │   └── sma_cross.py               # SMA crossover demo (fast/slow/allow_short)
│   └── tests/
│       └── test_engines.py            # 33 tests
│
├── ml/                                # Scaffolded; all subdirs empty
│   ├── feature_store/
│   ├── models/
│   │   ├── hmm/                       # Hidden Markov Model (regime detection)
│   │   ├── lstm/
│   │   ├── transformer/
│   │   └── xgboost/
│   ├── serving/
│   ├── training/
│   └── experiments/
│
├── engine/                            # C++ OMS — empty; future phase
│
├── infra/
│   ├── docker/
│   │   ├── init-timescaledb.sql       # Hypertable init; runs on first container start
│   │   ├── nginx.conf
│   │   └── setup-timescaledb.sql
│   ├── k8s/                           # Empty; future deployment phase
│   └── monitoring/
│       ├── prometheus.yml             # Scrapes backend /metrics, Redis, PostgreSQL, Celery
│       └── grafana/
│           ├── dashboards/
│           │   └── platform-health.json  # Pre-built Grafana dashboard
│           └── provisioning/
│               ├── dashboards.yml
│               └── datasources.yml
│
├── docs/
│   ├── architecture/
│   │   └── database-schema.md
│   ├── decisions/                     # ADRs (to be expanded)
│   └── developer/                     # Setup guides (to be expanded)
│
├── tests/
│   ├── e2e/                           # Cross-service Playwright tests (future)
│   └── load/                          # k6 WebSocket load tests (future)
│
└── .github/
    └── workflows/
        └── ci.yml                     # 4 jobs: backend, frontend, e2e, live-data
```

---

## 5. Database Schema

### 5.1 TimescaleDB Hypertables

```sql
-- OHLCV bars — primary time-series store
CREATE TABLE ohlcv (
    time        TIMESTAMPTZ     NOT NULL,
    symbol      TEXT            NOT NULL,
    exchange    TEXT            NOT NULL,
    asset_class TEXT            NOT NULL,  -- equity, crypto, forex, futures, options
    timeframe   TEXT            NOT NULL,  -- 1m, 5m, 15m, 1h, 4h, 1d, 1w
    open        NUMERIC(20, 8)  NOT NULL,
    high        NUMERIC(20, 8)  NOT NULL,
    low         NUMERIC(20, 8)  NOT NULL,
    close       NUMERIC(20, 8)  NOT NULL,
    volume      NUMERIC(30, 8)  NOT NULL,
    vwap        NUMERIC(20, 8),
    trade_count INTEGER,
    provider    TEXT            NOT NULL,
    PRIMARY KEY (time, symbol, timeframe)
);

SELECT create_hypertable('ohlcv', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON ohlcv (symbol, timeframe, time DESC);

-- Continuous aggregate: 1m → daily rollup
CREATE MATERIALIZED VIEW ohlcv_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    first(open, time)  AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, time)  AS close,
    sum(volume)        AS volume
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY bucket, symbol;
```

See `infra/docker/init-timescaledb.sql` for the full initialization script.

### 5.2 PostgreSQL Relational Tables

| Table | Purpose | Notes |
|---|---|---|
| `users` | Authentication, RBAC roles | `id UUID`, `email`, `password_hash`, `totp_secret`, `role`, `is_active` |
| `watchlists` | User symbol lists | `user_id FK`, `name`, `symbols TEXT[]`, `is_default` |
| `alerts` | Price/indicator trigger rules | `condition JSONB`, `is_active`, `triggered_at` |
| `dashboard_layouts` | Persisted panel grid configs | `layout JSONB` (react-grid-layout format) |
| `portfolios` | Portfolio containers | `initial_capital`, `currency` |
| `positions` | Open/closed positions | `side`, `avg_entry_price`, `stop_loss`, `take_profit` |
| `fundamentals` | Daily fundamental snapshots | `pe_ratio`, `market_cap`, `sector` etc. |
| `economic_events` | Calendar events | `impact HIGH/MEDIUM/LOW`, `forecast`, `actual` |
| `audit_log` | Security audit trail | Records: `auth.login_success/failed`, `auth.logout`, `auth.totp_enabled/failed` |
| **`orders`** ★ | Paper trading order lifecycle | `status`: pending→submitted→filled/cancelled/rejected |

### 5.3 Redis Key Structures

```
quote:{symbol}                   → {price, bid, ask, volume, change_pct, timestamp}
channel:quotes:{symbol}          → pub/sub broadcast
channel:tape:{symbol}            → tick stream
channel:orderbook:{symbol}       → Level 2 updates
channel:alerts:{user_id}         → triggered alert push
orders:{user_id}                 → ★ order status updates pub/sub
ratelimit:{ip}:{endpoint}        → sliding window counter
session:{token_jti}              → refresh token record (TTL = 7 days)
sentiment:{symbol}               → composite score (TTL = 5 min)
screener:{filter_hash}           → screener result cache (TTL = 60s)
bar:{symbol}:{timeframe}:latest  → latest OHLCV bar hash
```

### 5.4 MongoDB Collections

```javascript
// news_articles
{
  source: "benzinga" | "newsapi" | "reddit" | "sec_edgar",
  headline, body, url,
  published_at: ISODate,
  tickers_mentioned: [String],
  sentiment: {
    finbert_score, finbert_confidence,
    openai_score, openai_confidence,
    composite_score,
    label: "bullish" | "bearish" | "neutral",
    impact_category: "earnings" | "macro" | "regulatory" | "ma" | "analyst" | "general"
  }
}

// ticker_sentiment_aggregate
{
  symbol: String,
  score_1h, score_4h, score_1d,
  article_count_1h, article_count_1d,
  dominant_label, top_articles: [ObjectId]
}
```

---

## 6. Full API Contract

### REST — All Endpoints (auth-gated unless noted)

#### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Email + password + optional TOTP; returns access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Revoke all user tokens |
| GET  | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/auth/totp/setup` | Generate TOTP QR |
| POST | `/api/v1/auth/totp/verify` | Activate TOTP |

#### Market Data
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/market/quotes` | Batch quotes: `?symbols=AAPL,MSFT` |
| GET | `/api/v1/market/bars/{symbol}` | OHLCV: `?timeframe=1h&start&end&limit` |
| GET | `/api/v1/market/search` | Symbol search: `?q=apple&asset_class=equity` |
| GET | `/api/v1/market/snapshot/{symbol}` | Quote + fundamentals + sentiment |
| GET | `/api/v1/market/tape/{symbol}` | Recent prints |
| GET | `/api/v1/market/orderbook/{symbol}` | Level 2 depth |

#### Backtesting ★ New
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/backtest/run` | Run vectorized or event-driven backtest; optional Monte Carlo |
| POST | `/api/v1/backtest/wfo` | Walk-forward optimization with param grid |

#### Orders ★ New (paper trading)
| Method | Endpoint | Description |
|---|---|---|
| POST   | `/api/v1/orders` | Place market/limit/stop/stop_limit order |
| GET    | `/api/v1/orders` | List orders: `?symbol=AAPL&status=filled` |
| GET    | `/api/v1/orders/{id}` | Get specific order |
| DELETE | `/api/v1/orders/{id}` | Cancel open order |

#### Options
| GET | `/api/v1/options/chain/{symbol}` | Full chain with Greeks: `?expiry=2025-01-17` |
| GET | `/api/v1/options/expirations/{symbol}` | Available expiry dates |
| GET | `/api/v1/options/iv-surface/{symbol}` | Volatility surface |
| GET | `/api/v1/options/unusual-activity` | Unusual flow: `?min_premium=100000` |

#### Portfolio, Screener, Macro, Crypto, Alerts, Watchlist
> All endpoints from the original contract remain — see `backend/app/api/v1/` for implementation.

### WebSocket — All Feeds
| Endpoint | Token | Description |
|---|---|---|
| `/ws/market?token=jwt` | Required | Quote updates fan-out; subscribe/unsubscribe by symbol array |
| `/ws/tape?token=jwt` | Required | Time & sales stream |
| `/ws/orderbook/{symbol}?token=jwt` | Required | Level 2 updates |
| `/ws/alerts?token=jwt` | Required | Triggered alert push |
| `/ws/orders?token=jwt` | Required ★ | Live order status updates (Redis pub/sub per user) |

### Backtest Request Schema
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start": "2022-01-01",
  "end": "2024-01-01",
  "strategy": "sma_cross",
  "params": { "fast": 20, "slow": 50, "allow_short": false },
  "engine": "vectorized",
  "initial_capital": 100000.0,
  "commission": 0.001,
  "run_monte_carlo": true,
  "mc_simulations": 500
}
```

---

## 7. Architecture Invariants

These rules must not be broken. Any code change that violates them is a bug.

| Rule | Location |
|---|---|
| All secrets from env vars — zero hardcoded credentials | `.env`; `.gitignore` |
| `CurrentUser` dependency on every API route | `dependencies.py`; verified in all 13 v1 routers |
| Rate limiter applied globally | `middleware/rate_limit.py`; auth 10/60s, API 120/60s per IP |
| All ports bound to `127.0.0.1` in Docker | `docker-compose.yml` |
| Generic exception handler returns opaque error — no stack traces to clients | `main.py` |
| Single `MarketDataProvider` WebSocket per session | `providers/MarketDataProvider.tsx`; Zustand distribution |
| NLP (FinBERT/GPT-4o) never runs on the request path | Celery workers only; REST reads Redis cache |
| All market data flows through `services/market_data/router.py` | Provider abstraction |
| Backtesting engine imported lazily from API routes | Not at module level — avoids circular imports |
| Orders fallback to simulation when Alpaca keys absent | `services/orders/service.py`; no path requires live credentials |
| Audit log wired into all auth events | `api/v1/auth.py` → `services/audit/logger.py` → `audit_log` table |

---

## 8. Known Quirks & Suppressions

| Quirk | Location | Reason |
|---|---|---|
| `bcrypt` used directly instead of `passlib` wrapper | `auth/password.py` | passlib[bcrypt] compatibility bug |
| `black_scholes_greeks()` uppercase params S, K, T | `services/options/greeks.py` | Standard BS notation; `# noqa: N803` required |
| Long lines in data files | `screener/universe.py`, `screener/evaluator.py`, `data/crypto.py` | Pure data literals; `# noqa: E501` |
| `class Foo(str, Enum)` | Various | `# noqa: UP042` on all string-enum declarations |
| `random.uniform()` in demo data generators | Demo/data files | `# noqa: S311` + `# nosec B311`; not cryptographic |
| `detect-object-injection` ESLint rule disabled | `eslint.config.mjs` | TypeScript false-positive on `arr[i]` indexed access |
| `EconomicCalendarPanel` countdown renders `"${days}D"` | `EconomicCalendarPanel/index.tsx` | Intentional — matches test assertion |
| `MultiTimeframePanel` mocked in vitest | `tests/unit/panels_new.test.tsx` | `lightweight-charts` calls canvas/rAF APIs unavailable in jsdom; real rendering tested in Playwright E2E |

---

## 9. Validation State (Updated — ST-A through ST-G complete)

All checks are green on `main`.

```
Backend (from backend/):
  ruff check app/ tests/           → 0 findings
  ruff format --check app/ tests/  → 98 files already formatted
  bandit -r app/ -ll               → No issues identified; 0 High/Med/Low
  pytest tests/ -q                 → 70 passed, 2 skipped  ★ +6 new (ST-A/B)
                                     (2 skipped = test_migrations.py needs real PostgreSQL)

Backtesting (from repo root):
  uv run --project backend \
    python -m pytest backtesting/tests/ -q  → 53 passed  ★ +20 new (ST-E)

Frontend (from frontend/):
  npx vitest run                   → 144 passed (6 files)  ★ +24 new (ST-C/D/F/G)
  npm run lint                     → 0 errors, 0 warnings
  npx tsc --noEmit                 → 0 errors
  npm run build                    → compiled successfully
```

### CI Jobs
| Job | Trigger | Steps |
|---|---|---|
| `backend` | Every push/PR to main/develop | ruff check, ruff format, bandit, pytest |
| `frontend` | Every push/PR | npm ci, eslint, tsc, vitest, next build |
| `e2e` | After frontend passes | Playwright chromium, `auth.spec.ts` (no credentials) |
| `live-data` | Only when `ALPACA_SECRET_KEY` secret exists | pytest integration tests with real API keys |

---

## 10. Development Workflow

### Quick Start
```bash
# 1. Configure secrets
cp .env.example .env
# Edit .env: set JWT_SECRET_KEY, POSTGRES_PASSWORD, MONGO_PASSWORD, GRAFANA_ADMIN_PASSWORD
# Create frontend/.env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   NEXT_PUBLIC_WS_URL=ws://localhost:8000

# 2. Start full stack
make dev                   # docker compose up --build

# 3. Run migrations (first time)
make migrate               # alembic upgrade head

# 4. Verify
make test                  # pytest 64/64 + vitest 120/120
make lint                  # ruff + eslint + tsc

# 5. Access services
# App:        http://localhost:3000
# API docs:   http://localhost:8000/api/docs   (dev mode only)
# Grafana:    http://localhost:3001
# Prometheus: http://localhost:9090
```

### Test-specific commands
```bash
# Backend unit only
cd backend && /Users/henrynguyen/.local/bin/uv run python -m pytest tests/unit/ -q

# Backtesting engine
/Users/henrynguyen/.local/bin/uv run --project backend python -m pytest backtesting/tests/ -q

# Frontend unit only (fast)
cd frontend && npm run test -- --run

# E2E with credentials
TEST_USER_EMAIL=user@example.com TEST_USER_PASSWORD=secret \
  npx playwright test tests/e2e/
```

### Alembic migration workflow
```bash
make migrate-generate MSG="add_my_table"   # generate new migration
make migrate                                # apply all pending
make migrate-down                           # rollback one step
```

---

## 11. Environment Variables Reference

Copy `.env.example` to `.env`. All variables and their defaults are documented there. Below is the required-vs-optional breakdown:

| Variable | Required | Default / Notes |
|---|---|---|
| `JWT_SECRET_KEY` | **Required** | Min 32 chars — `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | **Required** | asyncpg DSN |
| `DATABASE_SYNC_URL` | **Required** | psycopg2 DSN (Alembic) |
| `REDIS_URL` | **Required** | — |
| `MONGODB_URL` | **Required** | — |
| `GRAFANA_ADMIN_PASSWORD` | **Required** | Change from `changeme` |
| `NEXT_PUBLIC_API_URL` | **Required (frontend)** | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | **Required (frontend)** | `ws://localhost:8000` |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Optional | Platform degrades to yfinance + simulated orders |
| `POLYGON_API_KEY` | Optional | Falls back to yfinance |
| `OPENAI_API_KEY` | Optional | Sentiment scoring falls back to FinBERT-only |
| `FRED_API_KEY` | Optional | Macro panel uses demo data |
| `ENABLE_METRICS` | Optional | Set `true` to expose `/metrics` to Prometheus |
| `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` | Optional | Enables live Playwright E2E tests |

---

## 12. Phased Roadmap — Original + Completed Additions

| Phase | Original goal | Status |
|---|---|---|
| 1 — Foundation | Auth + DB schema + dashboard shell | ✅ Complete |
| 2 — Data Layer + Core Charting | Market data + WS + ChartPanel + Watchlist | ✅ Complete |
| 3 — News + Sentiment | FinBERT + GPT-4o pipeline + NewsFeedPanel | ✅ Complete |
| 4 — Portfolio, Risk, Secondary Panels | Portfolio, Options, Order Book, Risk | ✅ Complete |
| 5 — Advanced Panels + Crypto | Screener, Alerts, Macro, HeatMaps, Crypto | ✅ Complete |
| 6 — Backtesting Framework | Vectorized + event-driven engines | ✅ Complete |
| 7 — Hardening + Enterprise Readiness | Security audit, Prometheus, CI | ✅ Complete |
| **8 — Order Management** ★ | Paper trading OMS + OrderEntryPanel | ✅ Complete |
| **9 — Performance Analytics** ★ | Win-rate gauge, P&L calendar, trade stats | ✅ Complete |
| **10 — Multi-Timeframe Analysis** ★ | 2×2 MTF chart grid | ✅ Complete |
| **11 — E2E Test Coverage** ★ | Playwright auth/dashboard/watchlist/chart | ✅ Scaffolded; auth-flow active in CI |

---

## 13. Outstanding Work — What Still Needs to Be Added

Completed in this session: **ST-A through ST-G** (7 sub-tasks). Items below represent remaining work.

### Completed ✅

- **ST-A** — `Order` model wired into Alembic autogenerate; `GET /api/v1/portfolio/trades` endpoint added; 3 new unit tests.
- **ST-B** — `backend/app/tasks/order_tasks.py` Celery beat task (`sync_open_orders`, every 10 s); 3 new unit tests.
- **ST-C** — `ChartCanvas.tsx` renders SMA/EMA/WMA/BB/RSI/MACD as lightweight-charts v5 `LineSeries` overlays; `ChartToolbar.tsx` gains "Ind ▾" dropdown + active pill row; 4 new vitest tests.
- **ST-D** — `BacktestPanel` frontend: form → `POST /api/v1/backtest/run` → equity curve + metrics grid + trade log; registered in dashboard + layoutStore; 7 new vitest tests.
- **ST-E** — `RSIMeanReversionStrategy`, `MACDCrossStrategy`, `BollingerBandStrategy`, `VWAPReversionStrategy` added to `backtesting/strategies/`; wired into `backtest.py` `_get_strategy()` and `_get_strategy_cls()`; 20 new pytest tests.
- **ST-F** — `Sparkline` SVG component (`frontend/components/ui/Sparkline.tsx`); `marketDataStore` gains `priceHistory: Record<string, number[]>` (last 20 prices, updated on each quote); `WatchlistPanel` rows now render sparklines; 6 new vitest tests.
- **ST-G** — `useWebSocket.ts` upgraded to exponential backoff with ±25% jitter (`backoffDelay()`, exported for testing); `onMaxRetriesExceeded` callback; backward-compatible `reconnectDelay` alias; 4 new vitest tests.

### Still outstanding

#### 13.4 E2E Tests with Live Credentials
The dashboard/watchlist/chart E2E tests (`e2e/*.spec.ts`) skip when `TEST_USER_EMAIL` is absent. To enable them:
1. Seed a test user in the development database
2. Add `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` to GitHub Actions repository secrets
3. Update `ci.yml` to start the backend stack for E2E (currently the `e2e` CI job runs without a backend)

#### 13.5 CI Secrets for Live Data
The `live-data` CI job exists but has no real API keys configured. To unlock real market-data tests in CI:
- Add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `POLYGON_API_KEY`, `FRED_API_KEY` to GitHub Actions repository secrets

### Medium priority

#### 13.8 Drawing Tools
`ChartToolbar.tsx` has timeframe/type/indicator controls but no drawing tools. The original spec planned TrendLine, Fibonacci, Pitchfork, Gann, Elliott Wave, and Annotations.

#### 13.9 Advanced Order Features
Current `OrderEntryPanel` supports basic order types. Missing:
- Bracket orders (entry + automatic stop-loss + take-profit in one submission)
- OCO (one-cancels-other) order pairs
- Order modification (change price/quantity of an open order)
- Real-time fill notifications → position auto-update in PortfolioPanel

#### 13.10 Volume Profile (VPVR)
The indicator spec includes Volume Profile Visible Range. This is a complex computation that requires per-bar data across the visible chart range. Needs: backend endpoint to compute VPVR for a symbol/range, and a custom lightweight-charts plugin for rendering.

#### 13.11 Volatility Surface Panel (VolatilityPanel)
Planned in Phase 5 but not built. A 3D IV surface using Three.js or D3 with WebGL — shows IV across strikes and expirations for the active symbol.

### Low priority

#### 13.12 Load Tests (k6)
`tests/load/` is empty. A k6 script targeting the WebSocket fan-out (`/ws/market`) is needed to validate the 1,000 concurrent subscribers goal.

#### 13.13 Additional Documentation
`docs/developer/` and `docs/decisions/` are empty. ADRs needed: frontend framework choice, database selection, WebSocket architecture, backtesting engine design.

#### 13.14 Kubernetes Manifests
`infra/k8s/` is empty. Needed when moving from Docker Compose to a cloud-native deployment.

---

## 14. New Ideas for Future Phases

These are new features not in the original plan, ranked by value-to-effort ratio.

### 14.1 Strategy Builder UI (Visual Signal Composer)
A drag-and-drop UI where users compose entry/exit logic from building blocks (indicators, comparators, conditions) without writing code. Each block maps to a Python class; the resulting configuration is serialized to JSON and sent to `POST /api/v1/backtest/run`. This is the bridge between the backtesting engine and non-programmers.

**Components needed:**
- `frontend/components/panels/StrategyBuilderPanel/` — node-based canvas (react-flow)
- `backend/app/api/v1/strategies.py` — CRUD for saved strategy configs
- `backtesting/strategies/dynamic.py` — runtime strategy constructor from JSON config

### 14.2 Bayesian Optimization (Optuna)
The current `WalkForwardOptimizer` uses grid search. Grid search is O(n^m) in the number of parameters. Adding Optuna Bayesian optimization would make parameter tuning practical for strategies with many parameters.
- File: `backtesting/optimization/bayesian.py`
- Use `optuna.create_study(direction="maximize")` with the backtesting engine as the objective
- Expose via `POST /api/v1/backtest/optimize`

### 14.3 Regime Detection (Hidden Markov Model)
The `ml/models/hmm/` directory is scaffolded. A trained HMM on VIX + yield-curve + momentum features can classify the current market regime (trending, mean-reverting, high-volatility, low-volatility). The regime state can:
- Tint the MacroPanel header with a regime color
- Filter which backtesting strategies are recommended
- Gate position sizing in the RiskPanel (reduce size in high-vol regimes)

### 14.4 Real-Time Indicator Streaming (Server-Sent Events)
Currently, indicator values are computed client-side in TypeScript. For shared signals (used in both the chart overlay and the backtesting engine), a server-side compute endpoint would provide consistency. A `GET /api/v1/market/indicators/{symbol}` endpoint using Python/TA-Lib, with results cached in Redis and refreshed each bar, would allow:
- Screener filter on live indicator values
- Alert conditions on indicator crossovers
- Regime detection inputs

### 14.5 AI Trade Journal
On every filled order, spawn a Celery task that:
1. Fetches the news sentiment at entry and exit time
2. Fetches the technical indicator state at entry (RSI, MACD, volume ratio)
3. Sends a structured prompt to GPT-4o: "Analyze this trade: entry conditions, market context, outcome"
4. Stores the response in MongoDB
5. Surfaces it in a new `TradeJournalPanel`

This creates a feedback loop that improves discipline without adding data entry burden.

### 14.6 WebSocket Resilience & Reconnect Strategy
Current `useWebSocket.ts` handles reconnects, but there is no exponential backoff with jitter, no circuit-breaker pattern, and no dead-letter queue for missed updates during a disconnect. A production-grade reconnect strategy should:
- Implement exponential backoff (100ms → 1.6s cap with ±25% jitter)
- Track "last received sequence number" per symbol
- On reconnect, request a replay of missed quotes since last sequence
- Emit a `connection_degraded` event to the Grafana alert channel

### 14.7 Portfolio Import (CSV + Broker API)
Users with existing positions elsewhere cannot use the PortfolioPanel meaningfully. A portfolio import system would:
- Accept a CSV upload (`symbol, quantity, avg_price, date_opened`)
- Accept OAuth tokens for TD Ameritrade, Interactive Brokers (via ibkr_web_api)
- Normalize all positions into the `positions` table
- Recalculate P&L against live quotes

### 14.8 Multi-User & Workspace Mode
The current auth system supports RBAC roles but everything is single-user. A workspace mode would:
- Add a `workspace` table (like a GitHub organization)
- Allow traders to share watchlists, screener presets, and alert configs
- Add a `workspace_admin` role that can invite/remove members
- Gate data cost: each workspace gets a pooled API rate limit

### 14.9 Terraform Cloud Deployment (AWS ECS)
`infra/k8s/` is empty but the Prometheus/Grafana observability stack is already production-ready. A Terraform IaC module for AWS ECS Fargate would provision:
- ECS services for backend, celery worker, frontend
- RDS PostgreSQL with TimescaleDB
- ElastiCache Redis
- DocumentDB (MongoDB-compatible)
- Application Load Balancer with ACM HTTPS
- Route 53 DNS
- Secrets Manager for all API keys
- CloudWatch alarms wired to Grafana

### 14.10 Tick Data Recorder + Replay
A background Celery task can record raw trade ticks from Alpaca/Polygon WebSocket into the `ticks` TimescaleDB hypertable. A "tape replay" mode in the backtesting engine would replay historical ticks at configurable speed, simulating intraday execution with realistic fill models. This is the foundation for microstructure-aware strategies.

---

## 15. Architecture Diagrams

### 15.1 System Overview (Updated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT BROWSER                                  │
│                       Next.js 16 App — 19 Panels                            │
│                                                                               │
│  Chart │ Watchlist │ Portfolio │ Risk │ OrderBook │ Tape │ Options │ News    │
│  Screener │ Alerts │ Macro │ Calendar │ HeatMap │ Correlation │ DarkPool     │
│  Crypto │ Performance ★ │ MultiTimeframe ★ │ OrderEntry ★                  │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                 │ HTTPS / WSS
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NGINX Reverse Proxy                                 │
│                 SSL · WebSocket Upgrade · Rate Limit                         │
└──────────────────────────────┬──────────────────────────────────────────────┘
                                │
              ┌─────────────────┼──────────────────────┐
              ▼                 ▼                       ▼
┌─────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  FastAPI REST   │  │  FastAPI WebSocket   │  │   Celery Workers     │
│  + Backtest API │  │  /ws/market          │  │  sentiment_tasks     │
│  + Orders API   │  │  /ws/tape            │  │  data_tasks          │
│  (Uvicorn)      │  │  /ws/orderbook       │  │  alert_tasks         │
└────────┬────────┘  │  /ws/alerts          │  │  order_tasks (todo)  │
         │           │  /ws/orders ★        │  └──────────────────────┘
         │           └──────────┬───────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────┐
│               Redis 7                   │
│  pub/sub · quote cache · rate limiter   │
│  refresh tokens · order status chan ★   │
└────────────────┬────────────────────────┘
                 │
     ┌───────────┼────────────────────────────┐
     ▼           ▼                            ▼
┌──────────┐ ┌──────────────┐      ┌──────────────────┐
│TimescaleDB│ │ PostgreSQL   │      │    MongoDB        │
│OHLCV/Tick │ │ Users/Orders │      │ News/Sentiment    │
└──────────┘ └──────────────┘      └──────────────────┘
     ▲
     │  Data Ingestion (scheduler + normalizer + writer)
     │
┌────┴───────────────────────────────────────────────────┐
│                   External Data APIs                    │
│  Alpaca · Polygon · yfinance · Binance · CoinGecko     │
│  NewsAPI · Benzinga · FRED · Unusual Whales             │
└────────────────────────────────────────────────────────┘

           Observability Stack:
┌──────────────────────────────────────┐
│  Prometheus :9090 ← /metrics         │
│  Grafana    :3001 (pre-provisioned)  │
└──────────────────────────────────────┘
```

### 15.2 Backtesting Engine Data Flow ★ New

```
POST /api/v1/backtest/run
        │
        ├── _fetch_data()
        │       └── get_provider() → AlpacaProvider or YFinanceProvider
        │               └── get_bars() → list[CanonicalBar]
        │                       └── DataFrame (open/high/low/close/volume)
        │
        ├── _get_strategy("sma_cross", params)
        │       └── SmaCrossStrategy(fast=20, slow=50)
        │               └── generate_signals(data) → pd.Series of +1/0/-1
        │
        ├── VectorizedEngine.run(data, strategy)
        │       └── NumPy one-pass: position tracking → equity curve → Trade list
        │
        ├── BacktestResult.compute_metrics()
        │       └── Sharpe, Sortino, Calmar, MaxDD, WinRate, ProfitFactor
        │
        └── MonteCarlo.run(result)  [optional]
                └── Bootstrap P&L → p05/median/p95 equity, drawdown, Sharpe
```

### 15.3 Order Lifecycle ★ New

```
OrderEntryPanel (frontend)
        │
        POST /api/v1/orders
        │
        ├── OrderRequest validation
        │
        ├── place_order(req)
        │       ├── _is_alpaca_available()?
        │       │     YES → POST https://paper-api.alpaca.markets/v2/orders
        │       │     NO  → Simulate immediate fill (demo mode)
        │       └── OrderResult
        │
        ├── Persist Order → PostgreSQL orders table
        │
        └── Return OrderResponse → frontend
                │
                WS /ws/orders → real-time fill updates (via Celery task — TODO)
```

---

## 16. Risk Register

| Risk | Severity | Mitigation | Status |
|---|---|---|---|
| API rate limits — free-tier throttling | High | Multi-provider fallback in `market_data/router.py`; Redis caching | ✅ Mitigated |
| WebSocket fan-out memory pressure | High | Redis pub/sub single source; thin WS handlers; Zustand slice selectors | ✅ Mitigated |
| NLP inference blocking request path | High | Celery workers; REST reads Redis cache | ✅ Mitigated |
| JWT secret rotation locks out users | Medium | 15-min access tokens + 7-day refresh with Redis family rotation | ✅ Mitigated |
| Secrets in environment | High | env vars only; `.gitignore`; `.env.example` documents rotation | ✅ Mitigated |
| OpenAI/Anthropic API costs | Medium | FinBERT primary; GPT-4o gated to high-impact articles only | ✅ Mitigated |
| Browser memory growth (tick accumulation) | Medium | Sliding window in `marketDataStore` | ✅ Mitigated |
| Backtesting look-ahead bias | Medium | Event-driven engine: signal uses data `[0:i+1]`; fill uses `open[i+1]` | ✅ Mitigated |
| Missing `orders` table migration | **High** | Generate and run Alembic migration | ⚠️ **Outstanding** |
| Order status not updated after Alpaca fill | High | Celery polling task needed (`order_tasks.py`) | ⚠️ **Outstanding** |
| E2E tests not running in CI with backend | Medium | Add backend stack to CI `e2e` job when test credentials available | ⚠️ Outstanding |
| TimescaleDB chunk size tuning | Medium | 1-day chunks for 1m bars; continuous aggregates from day one | ✅ In schema |
| Provider data inconsistency | Medium | `provider` field on every bar; prefer paid providers | ✅ In normalizer |
| CORS misconfiguration | Medium | `ALLOWED_ORIGINS` from env; NGINX enforces independently | ✅ Mitigated |
| ML model inference latency (future) | Medium | Serving via dedicated `ml/serving/` FastAPI service; async results | ⏳ When ML added |
| Multi-user data isolation (future) | High | Workspace model + row-level security in PostgreSQL | ⏳ When multi-user |

---

## 17. Regulatory Notes

| Requirement | Detail | Status |
|---|---|---|
| Polygon.io redistribution | Free tier data cannot be redistributed. Multi-user deployment requires commercial license. | Single-user OK |
| Alpaca paper trading | No financial regulation required for paper trading | ✅ Paper only |
| Binance US restriction | Use `api.binance.us` for US users | ✅ In config |
| OpenAI usage policy | Platform must display disclaimer that AI scores are not investment advice | ⚠️ Disclaimer not yet added to UI |
| FINRA/SEC (if live trading added) | SEC Rule 15c3-5 pre-trade risk checks required | Deferred |
| Real-time data redistribution | Each provider requires review before multi-user deployment | Deferred |

---

## 18. Compute & Cost Estimates

### Local Development
- Minimum: 16 GB RAM, 8-core CPU, 50 GB SSD
- Docker Compose runs all 9 services
- GPU optional but beneficial for local FinBERT inference

### Cloud Deployment — Single User (Phase 9)

| Service | AWS Component | Spec | Est. Monthly |
|---|---|---|---|
| Next.js frontend | Vercel or EC2 t3.small | 2 vCPU, 2 GB | $0–$20 |
| FastAPI backend | EC2 t3.medium | 2 vCPU, 4 GB | ~$35 |
| Celery workers | EC2 c6i.large × 2 | 4 vCPU, 8 GB | ~$140 |
| TimescaleDB | RDS db.t3.medium, 100 GB gp3 | 2 vCPU, 4 GB | ~$65 |
| Redis | ElastiCache cache.t3.micro | 0.5 GB | ~$15 |
| MongoDB | Atlas M10, 10 GB | 2 vCPU, 2 GB | ~$57 |
| Prometheus + Grafana | Included in EC2 backend | — | $0 |
| Data transfer + misc | — | — | ~$20 |
| **Total** | | | **~$332–$352/month** |

### Scale-Up Path (Multi-User)
Add: Application Load Balancer (~$20), Auto Scaling Group for FastAPI, Redis Cluster mode, TimescaleDB read replicas, Kafka for tick data fan-out at high volume. Estimated: **$800–$1,500/month** depending on concurrent users.
