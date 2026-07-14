# Platform Completion Plan — QuantNexus

## Top-Level Overview

This plan resolves all stubbed, incomplete, and missing components identified in the platform audit, working in dependency order. Every item produces production-quality, test-covered code with no placeholders.

**Scope:** 7 priority groups, ~30 implementation tasks, spanning backend persistence, async task workers, external API adapters, backtesting tooling, frontend E2E tests, and ML model implementations.

**Non-goals:** Changing existing endpoint URLs, request shapes, or response shapes. Introducing new frameworks without justification.

## Confirmed Design Decisions

| # | Decision | Resolution |
|---|----------|------------|
| 1 | Alert acknowledgement tracking | Add explicit `acknowledged_at` nullable DateTime column via new Alembic migration `0003_add_alert_acknowledged_at.py` |
| 2 | PDF WeasyPrint system deps | Add `libpango`, `libcairo`, `libgdk-pixbuf` to `backend/Dockerfile` via `apt-get install weasyprint` |
| 3 | ML model weight storage | Celery task only (no inference in API process at training time); weights stored in `data/ml_weights/{model}/{ticker}.*` volume mounted separately from source |
| 4 | Implementation scope | All 20 sub-tasks implemented in a single agent run |
| 5 | E2E tests without credentials | Tests skip gracefully with `test.skip(...)` when `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` absent; **⚠️ REMINDER: after implementation, re-run E2E tests with real credentials set to fully validate all 4 specs** |

---

## Sub-Task Index

| # | Sub-Task | Priority | Status |
|---|----------|----------|--------|
| 1 | StrategyConfig ORM model + migration + DB-backed routes | P1a | [ ] pending |
| 2 | Workspace + WorkspaceMember ORM models + DB-backed routes | P1b | [ ] pending |
| 3 | Alerts — wire existing Alert model into routes + evaluator task | P1c | [ ] pending |
| 4 | `refresh_ohlcv` Celery task — full implementation | P2a | [ ] pending |
| 5 | `record_ticks` Celery task — complete write path + batching | P2b | [ ] pending |
| 6 | Polygon.io adapter for options chain | P3a | [ ] pending |
| 7 | CoinGecko adapter for crypto data | P3b | [ ] pending |
| 8 | Binance adapter for crypto trading data | P3c | [ ] pending |
| 9 | FRED adapter for macro data (Redis cache) | P3d | [ ] pending |
| 10 | GridSearchOptimizer extraction | P4a | [ ] pending |
| 11 | PDF report generator + endpoint | P4b | [ ] pending |
| 12 | Playwright E2E — auth.spec.ts | P5a | [ ] pending |
| 13 | Playwright E2E — trading.spec.ts | P5b | [ ] pending |
| 14 | Playwright E2E — backtesting.spec.ts | P5c | [ ] pending |
| 15 | Playwright E2E — watchlist.spec.ts (full) | P5d | [ ] pending |
| 16 | LSTM price prediction model + endpoints | P6a | [ ] pending |
| 17 | XGBoost signal classifier + endpoints | P6b | [ ] pending |
| 18 | Transformer ADR (deferral document) | P6c | [ ] pending |
| 19 | Fibonacci retracement chart drawing tool | P7a | [ ] pending |
| 20 | Trendline chart drawing tool | P7b | [ ] pending |

---

## Sub-Task 1 — StrategyConfig ORM model + migration + DB-backed routes

**Intent:** The strategy builder panel currently saves to an in-memory dict that is lost on restart. Replace with a real PostgreSQL-backed persistence layer.

**Expected Outcomes:**
- `backend/app/models/strategy_config.py` exists with a `StrategyConfig` SQLAlchemy model
- `backend/models/__init__.py` imports `StrategyConfig` (so Alembic autogenerates)
- New Alembic migration creates the `strategy_configs` table (reversible)
- `strategies.py` routes use `AsyncSession` DB queries instead of `_STORE` dict
- All existing strategy endpoint contracts (GET list, POST create, GET by ID, DELETE) unchanged
- Existing tests continue to pass; 2 new tests added (happy path + not-found)

**Todo List:**
1. Create `backend/app/models/strategy_config.py` with `StrategyConfig` model
   - Fields: `id` (UUID PK, default uuid4), `user_id` (FK → users.id CASCADE), `name` (String 100, non-null), `description` (Text, nullable), `config` (JSONB, non-null — stores `{nodes, edges}`), `is_active` (Boolean, default True), `created_at` (DateTime server_default now()), `updated_at` (DateTime server_default now(), onupdate now())
2. Add `StrategyConfig` import to `backend/app/models/__init__.py` and `__all__`
3. Generate Alembic migration: `alembic revision --autogenerate -m "add_strategy_configs"`
   - Verify both `upgrade()` and `downgrade()` are correct
4. Rewrite `backend/app/api/v1/strategies.py`:
   - Import `DBSession` from `app.dependencies`
   - Replace `_STORE` dict operations with `db.execute(select(StrategyConfig)...)`, `db.add(...)`, `db.delete(...)` calls
   - Keep all existing `StrategyResponse` / `StrategyListResponse` Pydantic schemas unchanged
   - Keep `SaveStrategyRequest` shape unchanged (name, description, config)
   - Keep the `{nodes, edges}` validation logic
5. Write 2 unit tests in `backend/tests/unit/test_strategies.py`:
   - Happy path: POST creates strategy, GET list returns it, GET by ID returns it, DELETE removes it
   - Error case: GET/DELETE non-existent strategy ID returns 404

**Relevant Context:**
- Model pattern: see `backend/app/models/alert.py` — UUID PK, ForeignKey to users, JSONB column, mapped_column style
- Route pattern: see `backend/app/api/v1/portfolio.py` for DBSession injection example
- `app.dependencies.DBSession` = `Annotated[AsyncSession, Depends(get_db)]`
- Test pattern: see `backend/tests/` conftest.py for session setup
- Migration pattern: `backend/migrations/versions/0002_add_workspaces.py`

---

## Sub-Task 2 — Workspace + WorkspaceMember ORM models + DB-backed routes

**Intent:** The workspace migration (`0002_add_workspaces.py`) already created the tables. The routes still use in-memory dicts. Wire them to the database and enforce ownership/RBAC.

**Expected Outcomes:**
- `backend/app/models/workspace.py` with `Workspace` and `WorkspaceMember` models matching the existing DDL exactly (so no new migration is needed)
- `backend/app/models/__init__.py` imports both models
- `workspaces.py` routes use DB queries with ownership enforcement
- Role enum validated against: `owner`, `editor`, `viewer` (extend existing `member` default in migration if needed, or accept it as legacy)
- Workspace layout (JSONB) field supported in GET/PUT — align with `CreateWorkspaceRequest` schema (add optional `layout` field)
- Existing endpoint signatures preserved: GET list, POST create, DELETE by ID, POST members, GET members
- 2 new tests: happy path CRUD + forbidden delete by non-owner

**Todo List:**
1. Create `backend/app/models/workspace.py`:
   - `Workspace`: id (UUID PK), name (String 100), owner_id (FK → users), layout (JSONB nullable), created_at, updated_at
   - `WorkspaceMember`: workspace_id + user_id (composite PK), role (String 50), joined_at
   - Ensure column names/types match the DDL in `0002_add_workspaces.py` exactly (no new migration needed)
2. Add imports to `backend/app/models/__init__.py`
3. Rewrite `backend/app/api/v1/workspaces.py`:
   - List: query workspaces where user is owner OR is in workspace_members
   - Create: insert Workspace + auto-insert WorkspaceMember with role="owner"
   - Delete: verify `owner_id == current_user["sub"]` before delete (cascade handles members)
   - Invite: verify caller is owner, check no duplicate member, insert WorkspaceMember
   - List members: query WorkspaceMember by workspace_id; verify workspace exists
   - Validate `role` input against allowed values: `editor`, `viewer` (owner only via create)
4. Write 2 unit tests in `backend/tests/unit/test_workspaces.py`:
   - Happy path: create, invite member, list members, delete
   - Forbidden: non-owner cannot delete workspace (403)

**Relevant Context:**
- Existing migration DDL: `0002_add_workspaces.py` — workspace_members uses composite PK (workspace_id, user_id)
- The existing `WorkspaceResponse` schema has `id, name, owner_id, created_at` — preserve this
- `MemberResponse` has `workspace_id, user_id, role, joined_at` — preserve this
- `InviteMemberRequest` has `user_id, role` — preserve this

---

## Sub-Task 3 — Alerts: wire Alert ORM model + evaluator task

**Intent:** The `Alert` SQLAlchemy model exists in `alert.py` but `alerts.py` routes ignore it entirely and use `_ALERT_STORE` dict. The evaluator task (`alert_tasks.py`) returns a stub. Wire everything to the database and implement the evaluator.

**Expected Outcomes:**
- `alerts.py` routes use DB CRUD against the `Alert` model
- All endpoint shapes preserved exactly (including `triggered_at`, `status` field in responses)
- `alert_tasks.py` `evaluate_alerts()` task runs real evaluation: loads active alerts from DB, fetches latest prices from Redis quote cache, fires alerts that meet conditions
- Triggered alerts written back to DB (`triggered_at` set, `is_active` set to False)
- WebSocket `alerts_feed.py` receives the publish from the evaluator (already hooked via Redis pub/sub if the existing pattern is followed)
- A `AlertFireLog` model or equivalent approach so triggered alerts survive restarts (can use existing `Alert.triggered_at` + `is_active=False` as the log, no separate table needed)
- 2 unit tests: happy path alert CRUD + evaluator fires correct alert

**Todo List:**
1. Examine the existing `Alert` model fields (`alert.py`): id, user_id, symbol, alert_type, condition (JSONB), message, is_active, triggered_at, created_at
2. Note mismatch: routes use `threshold`, `label`, `status` fields not in the ORM model — reconcile:
   - Map `threshold` → store in `condition` JSONB as `{"field": "price", "op": "gte", "value": threshold}`
   - Map `label` → store in `message`
   - Map `status` → derive from `is_active` + `triggered_at` + acknowledgement flag (add `acknowledged_at` column via new migration, OR derive status as: PENDING if is_active and not triggered_at; TRIGGERED if triggered_at and not acknowledged; ACKNOWLEDGED via separate field)
   - Simplest: add `acknowledged_at` (DateTime nullable) column to alerts via new Alembic migration
3. Create migration `0003_add_alert_acknowledged_at.py` with `acknowledged_at` nullable DateTime column
4. Rewrite `alerts.py` routes to use DBSession:
   - `list_alerts`: `SELECT * FROM alerts WHERE user_id = :uid ORDER BY created_at DESC`
   - `create_alert`: insert new Alert row; derive status from is_active/triggered_at
   - `update_alert`: update threshold (condition JSONB), label (message), rearm (set is_active=True, triggered_at=None, acknowledged_at=None)
   - `delete_alert`: hard delete the row
   - `acknowledge_alert`: set `acknowledged_at = now()`
   - Helper `_alert_to_response()` to map ORM row → response dict (preserving existing response shape)
5. Implement `evaluate_alerts()` in `alert_tasks.py`:
   - Load all alerts where `is_active=True` and `triggered_at IS NULL`
   - For each alert: look up current price from Redis quote cache (`quote_cache.get_quote(symbol)`)
   - Evaluate condition using the existing `evaluator.evaluate_price_alert()` logic
   - For fired alerts: set `triggered_at = now()`, `is_active = False`, commit to DB
   - Publish fired alert to Redis pub/sub channel `alerts:{user_id}` so WebSocket picks it up
6. Register `evaluate_alerts` in Celery beat schedule (e.g., every 30 seconds)
7. Write 2 tests in `backend/tests/unit/test_alerts.py`:
   - CRUD happy path
   - Evaluator fires the correct alert given a price threshold

**Relevant Context:**
- `AlertType` and `AlertStatus` enums already defined in `backend/app/services/alerts/evaluator.py`
- Existing pub/sub pattern: see `backend/app/data/cache/pubsub.py`
- Quote cache: `backend/app/data/cache/quote_cache.py` — `get_quote(symbol)` returns latest price

---

## Sub-Task 4 — `refresh_ohlcv` Celery task

**Intent:** Currently returns `{"status": "pending_st5"}`. Implement full fetch-and-store: call Alpaca bars API (with yfinance fallback), write results to TimescaleDB.

**Expected Outcomes:**
- Task fetches OHLCV bars using existing `AlpacaProvider.get_bars()` (with `yfinance` fallback via `router.py`)
- Bars written to `ohlcv` table using existing `writer.write_bars()`
- Retry with exponential backoff: max 3 retries, base delay 5s, using Celery `autoretry_for`
- Dead-letter logging: on final failure, log structured error with symbol, timeframe, error
- WebSocket notification: publish `{"type": "ohlcv_refreshed", "symbol": ..., "timeframe": ..., "count": ...}` to Redis pub/sub channel `market:{symbol}` on completion
- Return dict with `{symbol, timeframe, bars_written, status}`
- 2 tests: successful fetch+write, graceful fallback when Alpaca unavailable

**Todo List:**
1. Rewrite `refresh_ohlcv` in `backend/app/tasks/data_tasks.py`:
   - Use `asyncio.run()` wrapper pattern (matching `_record_ticks_async` pattern already in file)
   - Import and use `AlpacaProvider` (or `MarketDataRouter`) to fetch bars
   - Import and use `write_bars` from `app.data.ingestion.writer`
   - Import and use `AsyncSessionLocal` for DB session
   - Add Celery retry: `@celery_app.task(name="tasks.refresh_ohlcv", bind=True, max_retries=3, default_retry_delay=5)`
   - On `httpx.HTTPError` or any network error: `raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))`
   - On final failure (max retries exceeded): log structured dead-letter entry
   - Publish WebSocket event via `pubsub.publish()` on success
2. Register `refresh_ohlcv` in Celery beat for common symbols (AAPL, SPY, etc.) — or leave as manually-invoked; ensure it's callable from the scheduler
3. Write tests in `backend/tests/unit/test_data_tasks.py`:
   - Mock AlpacaProvider returns bars → verify write_bars called with correct data
   - Mock AlpacaProvider raises → verify retry behavior and fallback to yfinance

**Relevant Context:**
- Existing async pattern: `_record_ticks_async()` / `asyncio.run()` in same file
- `AlpacaProvider.get_bars()`: `backend/app/services/market_data/alpaca.py`
- `write_bars()`: `backend/app/data/ingestion/writer.py`
- `AsyncSessionLocal`: `backend/app/database.py`
- Pub/sub: `backend/app/data/cache/pubsub.py`

---

## Sub-Task 5 — `record_ticks` Celery task — complete write path + batching

**Intent:** The WebSocket connection code exists and receives ticks but `_store_tick()` uses raw SQL with potential reliability issues. Add: batch insert buffering (500 ticks or 1s window), Prometheus metrics, and ensure the ticks hypertable schema is correctly set up.

**Expected Outcomes:**
- Tick inserts batched in memory; flushed when buffer hits 500 ticks OR 1 second has elapsed
- Prometheus counter `ticks_stored_total{symbol}` incremented per flush
- Prometheus gauge `tick_batch_size` recorded per flush
- Existing `_store_tick()` raw SQL replaced with batched async writer function
- 2 tests: batch flush at 500 items, batch flush at 1s timeout

**Todo List:**
1. Implement a `TickBatcher` class in `data_tasks.py`:
   - In-memory buffer (list of dicts), `max_size=500`, `max_age_seconds=1.0`
   - `add(tick)` method: append to buffer; flush if `len >= max_size` or `time_since_last_flush >= max_age_seconds`
   - `flush()` method: execute batch INSERT using `AsyncSessionLocal`, reset buffer + timer
2. Rewrite `_store_tick()` to route through `TickBatcher`
3. Add Prometheus metrics using the `prometheus_client` library already in the stack:
   - `ticks_stored_total` Counter with label `symbol`
   - `tick_batch_size` Histogram
4. Ensure ticks hypertable exists: verify against existing `init-timescaledb.sql` — if not present, add CREATE TABLE + `select create_hypertable(...)` to a new migration `0004_ensure_ticks_hypertable.py` (or verify it's in the initial schema migration already)
5. Write 2 tests in `backend/tests/unit/test_tick_batcher.py`

**Relevant Context:**
- Existing `_store_tick()` in `backend/app/tasks/data_tasks.py` — already has the INSERT SQL
- `Tick` ORM model in `backend/app/models/ohlcv.py` — has `time, symbol, price, size, side, exchange, provider`
- Initial schema migration creates both `ohlcv` and `ticks` hypertables — verify `ticks` is already there
- Prometheus: `prometheus_client` is pulled in via `prometheus-fastapi-instrumentator`

---

## Sub-Task 6 — Polygon.io adapter for options chain

**Intent:** The `/options/chain/{symbol}` and `/options/iv-surface/{symbol}` routes already have Polygon-conditional code paths but lack a dedicated adapter class following the codebase's provider pattern.

**Expected Outcomes:**
- `backend/app/services/options/polygon.py` adapter class implementing: `get_options_chain()`, `get_iv_surface()`, `get_greeks()` methods
- Options chain includes: calls and puts, strike ladder, expiration dates, delta/gamma/theta/vega if available from Polygon
- `options.py` routes delegate to the adapter when `POLYGON_API_KEY` is set, fall back to existing demo values when not
- Error handling: 429 → retry with 5s backoff (max 2 retries), timeout=10s, unexpected shape → log + demo fallback
- Unit tests with mocked Polygon responses: happy path + missing API key fallback

**Todo List:**
1. Create `backend/app/services/options/polygon.py`:
   - `PolygonOptionsAdapter` class
   - `async get_options_chain(symbol, expiry=None) -> dict`: calls `https://api.polygon.io/v3/reference/options/contracts` and `https://api.polygon.io/v2/snapshot/options/{symbol}`
   - `async get_iv_surface(symbol) -> list[dict]`: builds surface from options chain data
   - `_compute_greeks()` private helper using the existing `black_scholes_greeks()` from `app.services.options.greeks` when Polygon Greeks are absent
   - Rate limit handling: `httpx.AsyncClient` with timeout=10, catch 429 → retry 2x with 5s delay
2. Update `backend/app/api/v1/options.py`:
   - Import and instantiate `PolygonOptionsAdapter`
   - In `get_options_chain()`: when `settings.polygon_api_key` → call adapter; else → existing demo path
   - In `get_iv_surface()`: when `settings.polygon_api_key` → call adapter; else → `_build_demo_surface()`
3. Write `backend/tests/unit/test_polygon_adapter.py`:
   - Mock httpx response → verify parsed output shape
   - No API key → verify demo fallback returned

**Relevant Context:**
- Existing Greek computation: `backend/app/services/options/greeks.py`
- Existing options route: `backend/app/api/v1/options.py` — `_fetch_chain()`, `_build_demo_surface()` already exist
- Adapter pattern: see `backend/app/services/market_data/alpaca.py` and `yahoo_finance.py`

---

## Sub-Task 7 — CoinGecko adapter for crypto data

**Intent:** The `/crypto/*` routes have CoinGecko URL constants and some direct httpx calls scattered through `crypto.py`. Extract into a proper adapter with rate limiting.

**Expected Outcomes:**
- `backend/app/services/crypto/coingecko.py` adapter with: `get_price_stats()`, `get_ohlcv()`, `get_market_cap()`, `get_top_movers()`
- Token-bucket rate limiter: 50 calls/minute on free tier (configurable via `COINGECKO_RATE_LIMIT` env var)
- All 5 `/crypto/*` routes wire to adapter when available; existing synthetic generators preserved as fallback
- Error handling: 429 → wait for bucket refill, timeout=10s, unexpected response → log + fallback
- Unit tests: happy path + rate limit behavior

**Todo List:**
1. Create `backend/app/services/crypto/coingecko.py`:
   - `TokenBucket` class: `capacity=50`, `refill_rate=50/60` (tokens per second), thread-safe
   - `CoinGeckoAdapter` class with `base_url`, optional `api_key` (free tier works without key)
   - Methods: `get_coin_stats(coin_id)`, `get_ohlcv(coin_id, vs_currency, days)`, `get_top_movers(limit=10)`
   - All methods check token bucket; if empty, wait `time_until_next_token`
2. Create `backend/app/services/crypto/__init__.py` if not existing
3. Update `backend/app/api/v1/crypto.py`:
   - Replace direct `httpx.AsyncClient` CoinGecko calls with adapter
   - Keep `_demo_*` fallback functions; call them when adapter raises or key unavailable
4. Write `backend/tests/unit/test_coingecko_adapter.py`:
   - Happy path price fetch with mocked response
   - Rate limit: verify bucket depletes and waits correctly

**Relevant Context:**
- Existing crypto route: `backend/app/api/v1/crypto.py` — `COINGECKO_BASE = "https://api.coingecko.com/api/v3"`
- `settings.coingecko_api_key` field in `config.py`
- Demo fallback functions already in `crypto.py` — preserve them

---

## Sub-Task 8 — Binance adapter for crypto trading data

**Intent:** Order book and recent trades for crypto panels currently call Binance directly from route code. Extract into a structured adapter.

**Expected Outcomes:**
- `backend/app/services/crypto/binance.py` adapter with: `get_ticker()`, `get_order_book(depth=20)`, `get_recent_trades()`, `get_klines()`
- Adapter used as primary source for order book on crypto panels; secondary fallback behind CoinGecko for price data
- Error handling: timeout=10s, 429 → exponential backoff 2 retries, unexpected shape → log + empty response
- Unit tests with mocked Binance responses

**Todo List:**
1. Create `backend/app/services/crypto/binance.py`:
   - `BinanceAdapter` class
   - `async get_ticker(symbol) -> dict`: `GET /api/v3/ticker/24hr`
   - `async get_order_book(symbol, limit=20) -> dict`: `GET /api/v3/depth`
   - `async get_recent_trades(symbol, limit=50) -> list`: `GET /api/v3/trades`
   - `async get_klines(symbol, interval, limit=100) -> list`: `GET /api/v3/klines`
   - Use `settings.binance_api_key` when available for authenticated endpoints; graceful without key for public endpoints
2. Update `backend/app/api/v1/crypto.py` to use `BinanceAdapter` for funding rates and order book data
3. Write `backend/tests/unit/test_binance_adapter.py`:
   - Happy path order book with mocked response
   - Network timeout → returns empty dict

**Relevant Context:**
- Existing `BINANCE_BASE = "https://api.binance.us"` in `crypto.py`
- `settings.binance_api_key`, `settings.binance_secret_key` in `config.py`

---

## Sub-Task 9 — FRED adapter (Redis-cached macro data)

**Intent:** `macro/fred.py` already has correct FRED API logic but no caching. API calls happen on every request. Add Redis caching (TTL 1 hour) wrapping the existing functions.

**Expected Outcomes:**
- Every `fetch_series_latest()` and `fetch_series_history()` call checks Redis first (key: `fred:{series_id}`, TTL: 3600s)
- Cache miss: fetch from FRED API, store result in Redis
- When `FRED_API_KEY` absent: existing demo fallbacks unchanged
- All 5 `/macro/*` routes continue working identically from the consumer perspective
- 2 tests: cache hit returns cached value without HTTP call, cache miss fetches and stores

**Todo List:**
1. Add `_get_cached_or_fetch(series_id, fetch_fn, ttl=3600)` helper in `fred.py` using `redis.get` / `redis.setex` with JSON serialization
2. Wrap `fetch_series_latest()` and `fetch_series_history()` with the cache helper
3. Import `get_redis_pool` from `app.data.cache.redis_client` for async Redis access
4. No route changes needed — caching is transparent
5. Write `backend/tests/unit/test_fred_cache.py`:
   - Cache hit: mock redis.get returns value → no HTTP call made
   - Cache miss: mock redis.get returns None → HTTP called → redis.setex called

**Relevant Context:**
- Existing FRED service: `backend/app/services/macro/fred.py`
- Redis client: `backend/app/data/cache/redis_client.py`
- Docker Compose Redis service: `redis://redis:6379/0`

---

## Sub-Task 10 — GridSearchOptimizer extraction

**Intent:** Grid search logic is embedded inside `WalkForwardOptimizer._run_grid_search()`. Extract it into a standalone, independently usable class matching the `BayesianOptimizer` interface.

**Expected Outcomes:**
- `backtesting/optimization/grid_search.py` with `GridSearchOptimizer` class
- Same interface as `BayesianOptimizer`: `__init__(strategy_class, param_space, engine_cls, metric, ...)`, `run(data, symbol) -> GridSearchResult`, `results` property, `serialize() -> dict`
- `GridSearchResult` dataclass: `best_params`, `best_value`, `metric`, `all_results` (ranked list), `n_combinations`
- `WalkForwardOptimizer` refactored to import and use `GridSearchOptimizer` internally
- `backend/app/api/v1/backtest.py` optimizer route exposes `grid_search` as a new optimizer type (next to `bayesian`)
- 3 tests: full grid expansion, parameter validation (bad param raises), result ranking

**Todo List:**
1. Create `backtesting/optimization/grid_search.py`:
   - Extract `_expand_grid()` from `walk_forward.py` (or replicate it)
   - `GridSearchOptimizer` class implementing `run()` method: exhaustive cartesian product of `param_space`, evaluate each combination using `engine_cls`, rank by `metric`
   - `GridSearchResult` dataclass
   - `serialize()` method returns JSON-serializable dict
2. Refactor `backtesting/optimization/walk_forward.py` to call `GridSearchOptimizer` for its in-sample optimization step
3. Update `backend/app/api/v1/backtest.py`:
   - Add `"grid_search"` to optimizer type routing
   - Wire `POST /backtest/optimize` body `optimizer: "grid_search"` → `GridSearchOptimizer`
4. Write `backtesting/tests/test_grid_search.py` with 3 tests

**Relevant Context:**
- `_expand_grid()` in `backtesting/optimization/walk_forward.py` lines ~50-60
- `BayesianOptimizer` interface: `backtesting/optimization/bayesian.py`
- Backtest route: `backend/app/api/v1/backtest.py`

---

## Sub-Task 11 — PDF report generator + endpoint

**Intent:** The HTML report already captures all metrics. Add a PDF rendering layer using WeasyPrint (justified choice: it converts the existing HTML template directly without duplicating metric logic; ReportLab would require reimplementing all layouts).

**Expected Outcomes:**
- `backtesting/reporting/pdf_report.py` with `generate_pdf_report(result, mc_result=None) -> bytes`
- PDF includes: equity curve chart (SVG rendered inline), drawdown chart, full metrics table, trade log (first 100 trades), strategy parameter summary
- New endpoint `GET /api/v1/backtest/{run_id}/report/pdf` streams PDF as `application/pdf`
- PDF reuses `generate_html_report()` output — converts HTML → PDF via WeasyPrint
- `weasyprint` added to `backend/pyproject.toml` dependencies
- 2 tests: PDF bytes non-empty, correct Content-Type header returned from endpoint

**Todo List:**
1. Add `weasyprint>=65.0` to `backend/pyproject.toml` dependencies
2. Create `backtesting/reporting/pdf_report.py`:
   - `generate_pdf_report(result: BacktestResult, mc_result=None) -> bytes`
   - Call `generate_html_report(result, mc_result)` to get HTML string
   - Pass through `weasyprint.HTML(string=html).write_pdf()`
   - Return raw bytes
3. Store backtest results keyed by run_id: the existing `/backtest/run` endpoint returns results but does not store them for later retrieval — add in-memory or Redis-cached result store (TTL 1 hour) in `backtest.py`, keyed by a `run_id` UUID returned in the response
4. Update `BacktestRunResponse` schema to include a `run_id` field (non-breaking addition)
5. Add `GET /api/v1/backtest/{run_id}/report/pdf` endpoint:
   - Fetch stored result by `run_id` (404 if not found or expired)
   - Call `generate_pdf_report(result)`
   - Return `Response(content=pdf_bytes, media_type="application/pdf")`
6. Write 2 tests in `backend/tests/unit/test_pdf_report.py`

**Relevant Context:**
- HTML report: `backtesting/reporting/html_report.py` — `generate_html_report(result, mc_result=None) -> str`
- `BacktestResult` dataclass: `backtesting/engine/base.py`
- Backtest route: `backend/app/api/v1/backtest.py`

---

## Sub-Task 12 — Playwright E2E: auth.spec.ts

**Intent:** The existing `auth.spec.ts` has 4 basic tests but is missing the full audit requirements: TOTP second-factor prompt, JWT stored after login, logout clears session. Rewrite as a complete spec using Page Object Model.

**Expected Outcomes:**
- `frontend/tests/e2e/auth.spec.ts` fully rewritten with Page Object Model (`LoginPage` POM class)
- Tests cover: valid login → JWT in localStorage/cookie → redirect to dashboard; TOTP prompt appears when TOTP enabled; invalid credentials → error message visible; logout → session cleared → redirect to /login
- All tests use `LoginPage` POM, not bare `page.goto` + selectors
- Tests designed to pass with `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` env vars (skip gracefully without them)

**Todo List:**
1. Create `frontend/tests/e2e/poms/LoginPage.ts` — Page Object Model class:
   - Properties: `emailInput`, `passwordInput`, `submitButton`, `errorMessage`, `totpInput`
   - Methods: `goto()`, `login(email, password)`, `enterTotp(code)`, `expectError()`, `expectRedirectToDashboard()`
2. Rewrite `frontend/tests/e2e/auth.spec.ts`:
   - Import `LoginPage` POM
   - Test 1: valid login → dashboard redirect + access_token in storage
   - Test 2: TOTP prompt (conditional on TOTP_TEST_ENABLED env var)
   - Test 3: invalid credentials → error message
   - Test 4: logout → /login redirect + storage cleared
3. Preserve existing passing tests (they currently pass with minimal stubs)

**Relevant Context:**
- Existing `auth.spec.ts`: 4 tests for page load, invalid creds, redirects — keep these working
- `playwright.config.ts`: baseURL is `http://localhost:3000`, Chromium only
- Frontend auth: `frontend/middleware.ts` handles auth redirects

---

## Sub-Task 13 — Playwright E2E: trading.spec.ts

**Intent:** New spec file (does not exist). Create `trading.spec.ts` covering the paper order flow.

**Expected Outcomes:**
- `frontend/tests/e2e/trading.spec.ts` created (new file — not in existing stubs)
- Tests: place paper market buy order, verify order appears in orders panel, cancel order, verify cancellation status
- Uses Page Object Model: `OrderEntryPage` POM

**Todo List:**
1. Create `frontend/tests/e2e/poms/OrderEntryPage.ts` POM:
   - Methods: `selectSymbol(symbol)`, `selectSide(side)`, `selectOrderType(type)`, `enterQuantity(qty)`, `submitOrder()`, `expectOrderInTable(symbol)`, `cancelOrder(symbol)`, `expectOrderStatus(symbol, status)`
2. Create `frontend/tests/e2e/trading.spec.ts`:
   - Setup: login using `LoginPage` POM
   - Test 1: place market buy → order appears in orders panel
   - Test 2: cancel the order → status changes to "canceled"
   - Skip without TEST_USER credentials

**Relevant Context:**
- `OrderEntryPanel` component: `frontend/components/panels/OrderEntryPanel/`
- Backend orders endpoint: `POST /api/v1/orders` (Alpaca paper trading)

---

## Sub-Task 14 — Playwright E2E: backtesting.spec.ts

**Intent:** New spec file (not in existing stubs). Create `backtesting.spec.ts` covering the strategy builder + backtest run flow.

**Expected Outcomes:**
- `frontend/tests/e2e/backtesting.spec.ts` created
- Tests: navigate to strategy builder, configure SMA crossover parameters, run backtest, wait for completion (poll for results panel), verify equity curve chart renders, verify metrics table is populated
- Uses Page Object Model: `BacktestPage` POM

**Todo List:**
1. Create `frontend/tests/e2e/poms/BacktestPage.ts` POM:
   - Methods: `navigate()`, `selectStrategy(name)`, `setParam(key, value)`, `setDateRange(start, end)`, `runBacktest()`, `waitForResults(timeout)`, `expectEquityCurveVisible()`, `expectMetricsTablePopulated()`
2. Create `frontend/tests/e2e/backtesting.spec.ts`:
   - Test 1: configure + run SMA crossover backtest → equity curve visible
   - Test 2: metrics table has Sharpe, max drawdown values
   - Skip without TEST_USER credentials

**Relevant Context:**
- `BacktestPanel` component: `frontend/components/panels/BacktestPanel/`
- `StrategyBuilderPanel` component

---

## Sub-Task 15 — Playwright E2E: watchlist.spec.ts (full implementation)

**Intent:** The existing `watchlist.spec.ts` has only 2 skeleton tests (render input + type). Rewrite as complete CRUD test suite per the audit requirements.

**Expected Outcomes:**
- Rewritten `watchlist.spec.ts` with `WatchlistPage` POM
- Tests: add ticker → appears in list; remove ticker → disappears; duplicate ticker rejected (error shown)
- Skip gracefully without TEST_USER credentials

**Todo List:**
1. Create `frontend/tests/e2e/poms/WatchlistPage.ts` POM:
   - Methods: `addSymbol(symbol)`, `expectSymbolVisible(symbol)`, `removeSymbol(symbol)`, `expectSymbolAbsent(symbol)`, `expectDuplicateError()`
2. Rewrite `frontend/tests/e2e/watchlist.spec.ts`:
   - beforeEach: login via `LoginPage` POM
   - Test 1: add AAPL → visible in watchlist
   - Test 2: remove AAPL → no longer visible
   - Test 3: add duplicate → error shown

**Relevant Context:**
- Existing `watchlist.spec.ts`: 2 tests preserved in rewrite
- `WatchlistPanel` component

---

## Sub-Task 16 — LSTM price prediction model + endpoints

**Intent:** `ml/models/lstm/` directory is empty. Implement a working PyTorch LSTM for 3-class price direction prediction.

**Expected Outcomes:**
- `ml/models/lstm/model.py`: `LSTMPricePredictor` PyTorch model class
- `ml/models/lstm/dataset.py`: dataset builder from OHLCV + indicators
- `ml/models/lstm/train.py`: training loop, saves weights to `ml/models/lstm/weights/{ticker}.pt` (or S3 if `AWS_S3_BUCKET` set)
- `backend/app/api/v1/ml.py`: new router with `POST /ml/lstm/train` (Celery task) + `GET /ml/lstm/predict`
- Router registered in `backend/app/api/v1/router.py`
- `POST /ml/lstm/train` body: `{ticker, start, end, epochs=20, hidden_size=64, seq_len=30}`; launches Celery task, returns `{task_id}`
- `GET /ml/lstm/predict?ticker=X`: loads latest weights, returns `{ticker, up_prob, flat_prob, down_prob, prediction, confidence}`
- `torch` and `scikit-learn` added to `pyproject.toml`
- Minimum test: training runs without error on synthetic data; inference returns valid probability distribution summing to 1.0

**Todo List:**
1. Add `torch>=2.6.0`, `scikit-learn>=1.7.0` to `backend/pyproject.toml`
2. Create `ml/models/lstm/model.py`:
   - `LSTMPricePredictor(nn.Module)`: LSTM layers + linear classifier head → 3 output classes
   - Input: `(batch, seq_len, n_features)` where features = OHLCV normalized + technical indicators
   - Output: `(batch, 3)` softmax probabilities
3. Create `ml/models/lstm/dataset.py`:
   - `OHLCVDataset(Dataset)`: takes DataFrame of OHLCV+indicators, builds sliding windows of `seq_len` bars, labels = next-bar return class (up>1%, flat, down>1%)
   - `build_features(df: pd.DataFrame) -> pd.DataFrame`: compute SMA, RSI, MACD, volume ratio from OHLCV
4. Create `ml/models/lstm/train.py`:
   - `train_lstm(ticker, start, end, epochs, hidden_size, seq_len) -> Path` function
   - Fetches OHLCV data via yfinance (no Alpaca key needed in training context)
   - Trains model, saves weights
5. Create `backend/app/tasks/ml_tasks.py`:
   - `train_lstm_task(ticker, start, end, **kwargs)` Celery task wrapping `train_lstm()`
6. Create `backend/app/api/v1/ml.py`:
   - `POST /ml/lstm/train` → dispatch `train_lstm_task.delay(...)`, return `{task_id}`
   - `GET /ml/lstm/predict?ticker=X` → load weights, run inference, return probability dict
7. Register router in `backend/app/api/v1/router.py`
8. Write 2 tests in `backend/tests/unit/test_lstm.py`

**Relevant Context:**
- PyTorch version: `torch>=2.6.0` (latest stable as of 2026, CPU only for inference)
- Feature pipeline: reuse indicator logic from `backend/app/services/indicators/`
- Weight storage path: `ml/models/lstm/weights/{ticker}.pt`

---

## Sub-Task 17 — XGBoost signal classifier + endpoints

**Intent:** `ml/models/xgboost/` directory is empty. Implement binary signal classifier (long / no-position).

**Expected Outcomes:**
- `ml/models/xgboost/model.py`: training + inference wrapper
- `ml/models/xgboost/features.py`: feature engineering (OHLCV + indicators + lagged returns 1,3,5,10 bars)
- `backend/app/api/v1/ml.py` extended with: `POST /ml/xgboost/train`, `GET /ml/xgboost/predict`, `GET /ml/xgboost/features`
- `xgboost` added to `pyproject.toml`
- Feature importance endpoint returns non-empty ranked list
- 2 tests: train + predict on synthetic data

**Todo List:**
1. Add `xgboost>=2.1.0` to `backend/pyproject.toml`
2. Create `ml/models/xgboost/features.py`:
   - `build_xgb_features(df)`: same base indicators as LSTM + lagged returns at 1,3,5,10 bars
   - Returns labeled training DataFrame
3. Create `ml/models/xgboost/model.py`:
   - `XGBoostSignalClassifier`: wraps `xgb.XGBClassifier`
   - `train(df, label_col) -> None`, `predict(df) -> dict`, `get_feature_importance() -> list[dict]`
   - Saves model to `ml/models/xgboost/weights/{ticker}.json`
4. Create `backend/app/tasks/ml_tasks.py` (extend from Sub-Task 16):
   - `train_xgboost_task(ticker, start, end)` Celery task
5. Extend `backend/app/api/v1/ml.py`:
   - `POST /ml/xgboost/train` → Celery task dispatch
   - `GET /ml/xgboost/predict?ticker=X` → load model, inference
   - `GET /ml/xgboost/features?ticker=X` → feature importance ranked list
6. Write 2 tests in `backend/tests/unit/test_xgboost.py`

**Relevant Context:**
- XGBoost version: `xgboost>=2.1.0` (latest stable)
- Same feature pipeline as LSTM (Sub-Task 16's `build_features()` can be shared)
- Model weights: `ml/models/xgboost/weights/{ticker}.json`

---

## Sub-Task 18 — Transformer ADR (deferral)

**Intent:** Implement the formal deferral document for the Transformer model per the audit's "defer or implement" instruction. Given complexity, proper benchmarking infrastructure, and that LSTM + XGBoost cover the near-term requirements, defer.

**Expected Outcomes:**
- `docs/adr/ADR-005-transformer-deferral.md` created
- Covers: rationale for deferral, proposed architecture (vanilla encoder-only Transformer), data requirements, re-engagement criteria (when to revisit), comparison vs LSTM/XGBoost
- README ML section updated to reference ADR-005

**Todo List:**
1. Create `docs/adr/ADR-005-transformer-deferral.md` with standard ADR structure (Context, Decision, Consequences, Proposed Architecture, Re-engagement Criteria)
2. Update README.md ML section to mention LSTM, XGBoost (implemented), Transformer (deferred, see ADR-005)

**Relevant Context:**
- Existing ADRs in `docs/adr/` (ADR-001 through ADR-004)

---

## Sub-Task 19 — Fibonacci retracement chart drawing tool

**Intent:** Implement the Fibonacci retracement drawing tool in the charting panel. User clicks swing high then swing low; 7 Fibonacci levels are drawn as horizontal lines with labels. Persist to workspace layout.

**Expected Outcomes:**
- New `FibonacciTool` component in `frontend/components/panels/ChartPanel/`
- Fibonacci levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
- Integration with `lightweight-charts` API: use `ISeriesApi.createPriceLine()` for each level
- Lines persist: saved to workspace layout JSONB via `PUT /api/v1/workspaces/{id}` (after Sub-Task 2 wires the `layout` field)
- Individual line deletion supported
- Toolbar button to activate the tool (in `ChartToolbar.tsx`)
- TypeScript strict mode, no `any`

**Todo List:**
1. Create `frontend/components/panels/ChartPanel/FibonacciTool.tsx`:
   - `useFibonacciTool(chartRef)` hook: manages click state machine (waiting for high, waiting for low, drawing)
   - `drawFibLevels(chart, high, low)`: creates 7 price lines via lightweight-charts API
   - `clearFibLevels()`: removes existing price lines
   - Returns: `{activate, deactivate, clear, drawings}` — `drawings` is array of drawn level sets
2. Update `ChartToolbar.tsx`: add Fibonacci tool toggle button with icon
3. Update `ChartCanvas.tsx` or `index.tsx`: integrate `useFibonacciTool`, connect toolbar state
4. Wire persistence: when drawings change, dispatch workspace layout update (serialize drawings array to JSONB)
5. No new test required per audit scope (frontend tooling tests are covered by E2E specs)

**Relevant Context:**
- `lightweight-charts` v5: `ISeriesApi.createPriceLine({price, color, lineWidth, title})`
- Workspace layout: saved to `Workspace.layout` JSONB field (Sub-Task 2)
- `ChartPanel/index.tsx`, `ChartCanvas.tsx`, `ChartToolbar.tsx`

---

## Sub-Task 20 — Trendline chart drawing tool

**Intent:** Implement a trendline drawing tool. User clicks two points; a line is drawn and extended to the current bar. Persist to workspace layout. Show price tooltip on hover.

**Expected Outcomes:**
- `TrendlineTool.tsx` component in `ChartPanel/`
- User click flow: click point A → click point B → line drawn connecting both, extended rightward
- Hover tooltip shows price value at cursor x-position
- Persists in workspace layout JSON alongside Fibonacci drawings
- Toolbar button to activate (in `ChartToolbar.tsx`)
- Individual deletion supported

**Todo List:**
1. Create `frontend/components/panels/ChartPanel/TrendlineTool.tsx`:
   - `useTrendlineTool(chartRef)` hook: 2-click state machine
   - Line rendering: use `lightweight-charts` custom series or overlay canvas (lightweight-charts v5 supports custom plugins — use `IChartApi.addLineSeries()` for the trendline)
   - `extendToPresent(point1, point2, currentBarTime)`: extrapolate slope to latest bar
   - Hover tooltip: subscribe to chart `crosshairMove` event → compute price on trendline at x
2. Update `ChartToolbar.tsx`: add trendline tool toggle button
3. Update `ChartCanvas.tsx` / `index.tsx`: integrate `useTrendlineTool`
4. Wire persistence: serialize trendlines alongside Fibonacci levels in workspace layout

**Relevant Context:**
- `lightweight-charts` v5 API: `chart.addLineSeries({color, lineWidth})`, `series.setData([{time, value}])`
- Coordinate system: lightweight-charts uses bar time on x-axis; slope is in price/bar units
- `ChartPanel/ChartCanvas.tsx`, `ChartToolbar.tsx`

---

## Implementation Notes

### Technology Justifications (New Libraries)
- **`weasyprint`** (Sub-Task 11): Converts existing HTML report to PDF directly. Alternative (ReportLab) would require duplicating all layout and chart rendering logic. WeasyPrint is actively maintained (latest 2025), MIT license.
- **`torch`** (Sub-Task 16): PyTorch is the dominant framework for production LSTM models, actively maintained, Apache 2.0. No viable alternative for sequence models already suggested by the audit.
- **`xgboost`** (Sub-Task 17): Industry-standard gradient boosting library, actively maintained, Apache 2.0. The audit explicitly names xgboost as the required library.
- **`scikit-learn`** (Sub-Task 16): Required for data preprocessing (StandardScaler, train_test_split). Already a transitive dependency of hmmlearn; making it explicit.

### Dependency Order for Implementation
Sub-tasks must be implemented in this order to avoid blockers:
1. Sub-Tasks 1, 2, 3 (persistence layer) — Sub-Tasks 4, 5 can follow immediately after
2. Sub-Tasks 6, 7, 8, 9 (adapters) — independent, can run in parallel
3. Sub-Task 10 (grid search) — independent
4. Sub-Task 11 (PDF) — requires Sub-Task 10 to be stable (same backtesting package)
5. Sub-Tasks 12–15 (E2E) — require Sub-Tasks 1–3 to be DB-backed (auth + watchlist)
6. Sub-Tasks 16–18 (ML) — independent but benefit from Sub-Tasks 4/5 (data pipeline)
7. Sub-Tasks 19–20 (charts) — require Sub-Task 2 (workspace DB persistence)

### Security Compliance Notes
- All new API keys accessed via `settings.*` (pydantic-settings from env vars) — never hardcoded
- All new DB operations use parameterized SQLAlchemy queries — no string interpolation
- New endpoints use `CurrentUser` dependency for auth enforcement
- Celery tasks use structured logging (structlog) — no sensitive data in log messages
- WeasyPrint runs in the backend process; no user-supplied HTML accepted (only internal template)
- PyTorch model weights stored locally or S3 — never in DB or logs
