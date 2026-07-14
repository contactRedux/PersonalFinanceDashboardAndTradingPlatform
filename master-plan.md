# QuantNexus Master Plan — Unified Backlog & Execution Roadmap

**Final State:** All **183 backend + 204 frontend** tests pass. TypeScript clean.
All Tier 0, 1, 2, and 3 items complete. Tier 4 items are intentionally deferred (see §6).

---

## 0. Source Document Contradictions Found

The following contradictions were found between the summary document and the actual file system. The **file system wins**.

| Claim in summary | Actual state on disk |
|---|---|
| `bayesian.py` doesn't exist | `backtesting/optimization/bayesian.py` EXISTS — Bayesian optimizer (Optuna TPE) fully implemented |
| `pdf_report.py` doesn't exist | `backtesting/reporting/pdf_report.py` EXISTS — WeasyPrint-based, implemented in current sprint |
| `infra/k8s/` is empty | 7 K8s manifest files exist (`backend.yaml`, `celery-worker.yaml`, `frontend.yaml`, `ingress.yaml`, `namespace.yaml`, `redis.yaml`, `secrets.yaml`) |
| `infra/terraform/` is empty | 5 Terraform files exist (`main.tf`, `ecs.tf`, `alb.tf`, `variables.tf`, `outputs.tf`) |
| `tests/load/` is empty | `tests/load/rest_auth.js` and `ws_market.js` exist — real k6 code, 1,000-VU target configured |
| `docs/developer/` is empty | Contains `deployment.md` and `load-testing.md` |
| `docs/architecture/` is empty | Contains `database-schema.md` |
| Screener presets endpoints missing | Both `GET /screener/presets` and `POST /screener/presets` exist in `screener.py`, but `POST` is not DB-backed — saves nothing permanently |
| `GET /market/snapshot/{symbol}` implementation unclear | Implemented with real provider + Redis cache in `market.py` |
| ML subdirs are empty | `ml/models/lstm/`, `ml/models/xgboost/`, `ml/models/hmm/` all have real implementation files |
| `VolatilityPanel` not built | Implemented in `frontend/components/panels/VolatilityPanel/index.tsx` with real IV surface API call |
| Chart drawing tools: "toolbar has zero drawing tools" | `useFibonacciTool.ts` and `useTrendlineTool.ts` implemented; toolbar wired (completed in current sprint) |

---

## 1. Tier Classification

| Tier | Description |
|---|---|
| **Tier 0** | Blocking / In Progress — must complete before any Tier 1 work begins |
| **Tier 1** | High Priority — directly affects core trading platform usability |
| **Tier 2** | Medium Priority — expands capability, not blocking core workflows |
| **Tier 3** | Low Priority / Infrastructure — non-blocking, improves quality and ops |
| **Tier 4** | Long Horizon / Explicitly Deferred — requires prior phases or deliberate architecture work |

---

## 2. Tier 0 — Blocking / In Progress

### COMP-21 · CI Live-Data Secrets (was: CI Blocker)
- **Source:** `PLATFORM_STATUS.md:758`, `.github/workflows/ci.yml:99-130`
- **Current state:** CI references `secrets.ALPACA_API_KEY`, `secrets.ALPACA_SECRET_KEY`, `secrets.POLYGON_API_KEY`, `secrets.FRED_API_KEY` in the conditional live-data job. No evidence these secrets are set in the GitHub repository. The live-data integration test job silently skips if secrets are absent.
- **Acceptance criteria:**
  - All four secrets are added to the GitHub Actions repository secret store
  - The live-data job in `.github/workflows/ci.yml` runs `tests/integration/test_api.py` without the conditional skip
  - CI green badge reflects live-data tests passing
- **Complexity:** S
- **Dependencies:** None

### COMP-22 · E2E Tests with Live Credentials
- **Source:** `PLATFORM_STATUS.md:752`, `frontend/tests/e2e/` (6 spec files, all skip without `TEST_USER_EMAIL`/`TEST_USER_PASSWORD`)
- **Current state:** All 6 E2E specs (`auth.spec.ts`, `trading.spec.ts`, `backtesting.spec.ts`, `watchlist.spec.ts`, `chart.spec.ts`, `dashboard.spec.ts`) have real test logic but skip when `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` env vars are unset. CI runs `npx playwright test tests/e2e/auth.spec.ts` only; the other 5 specs are not run in CI at all.
- **Acceptance criteria:**
  - `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` added as CI secrets (or a seeded test user created and credentials committed to non-secret env)
  - All 6 E2E spec files added to the CI Playwright run (not just `auth.spec.ts`)
  - A pre-test step starts the backend (Docker Compose or `uvicorn` in the background) before Playwright runs
  - All 6 specs pass in CI with credential-gated tests executing (not skipping)
- **Complexity:** M
- **Dependencies:** COMP-21 (backend must be reachable by E2E tests)

---

## 3. Tier 1 — High Priority

### ST-J · Advanced Order Features
- **Source:** `PLATFORM_STATUS.md:767`, `next-sprint-plan.md`
- **Current state:** `backend/app/api/v1/orders.py` handles basic orders through Alpaca paper trading. Bracket orders and OCO pairs are referenced in the API but fill→portfolio auto-update is not wired. No order modification endpoint exists.
- **Acceptance criteria:**
  - `POST /orders` accepts bracket order params (`take_profit`, `stop_loss`) and submits to Alpaca
  - `POST /orders` accepts OCO pair params
  - `PATCH /orders/{order_id}` implements order modification (limit price, quantity)
  - When an order fill is received via the Alpaca WebSocket feed, the portfolio positions table is updated in PostgreSQL automatically (Celery task or WebSocket handler)
  - `backend/tests/unit/test_orders.py` has ≥ 4 tests covering bracket, OCO, modify, fill-update paths
- **Complexity:** M
- **Dependencies:** None

### ST-Q · Regime Detection HMM
- **Source:** `next-sprint-plan.md`, `ml/models/hmm/model.py`, `ml/models/hmm/train.py`
- **Current state:** `ml/models/hmm/model.py` and `ml/models/hmm/train.py` exist with real implementation. No backend API endpoints expose the HMM. No frontend component uses regime state.
- **Acceptance criteria:**
  - `POST /ml/hmm/train` — accepts ticker + date range, trains HMM via Celery task, stores model to `data/ml_weights/hmm/`
  - `GET /ml/hmm/regime?ticker=X` — returns current regime label (bull/bear/sideways) + probability
  - HMM regime overlay added to `ChartPanel` as a colored background band (e.g., green/red/grey)
  - 2 unit tests: training completes without error on 1 year SPY daily data; regime endpoint returns valid probabilities summing to 1.0
- **Complexity:** M
- **Dependencies:** None (HMM model already exists)

### ST-V · Indicator Library — Tier 1 Gaps (Momentum + Trend)
- **Source:** `trading-platform-plan.md:344-383`
- **Current state:** `frontend/lib/indicators/index.ts` exports 13 functions (SMA, EMA, WMA, DEMA, TEMA, HMA, MACD, RSI, BB, ATR, VWAP, OBV, HeikinAshi). The following high-priority indicators are missing: `stochasticRsi`, `cci`, `williamsR`, `parabolicSar`, `donchianChannel`, `keltnerChannel`.
- **Acceptance criteria:**
  - `frontend/lib/indicators/index.ts` exports `stochasticRsi(closes, highs, lows, period, smoothK, smoothD)`, `cci(highs, lows, closes, period)`, `williamsR(highs, lows, closes, period)`, `parabolicSar(highs, lows, step, max)`, `donchianChannel(highs, lows, period)`, `keltnerChannel(highs, lows, closes, atrPeriod, multiplier)`
  - Each function has corresponding unit tests in `frontend/tests/unit/indicators.test.ts` (≥ 2 assertions per function: edge case + known value)
  - All 6 new indicators appear in `INDICATOR_TYPES` in `ChartToolbar.tsx` so users can add them
  - Backend `backend/app/services/indicators/` has matching Python implementations for backtesting use
  - TypeScript strict mode passes with no `any` usage
- **Complexity:** M
- **Dependencies:** None

### ST-W · Indicator Library — Tier 1 Gaps (Volume + Structure)
- **Source:** `trading-platform-plan.md:344-383`
- **Current state:** Volume indicators are limited to OBV and VWAP (simple daily). Missing: `accumulationDistribution`, `cmf` (Chaikin Money Flow), `mfi` (Money Flow Index), `forceIndex`, `rvol` (Relative Volume), anchored VWAP variants, pivot points.
- **Acceptance criteria:**
  - `frontend/lib/indicators/index.ts` exports `accumulationDistribution`, `cmf`, `mfi`, `forceIndex`, `rvol`, `pivotPoints` (standard daily pivots: P, R1, R2, R3, S1, S2, S3)
  - Pivot point lines rendered as horizontal dashed price lines (use `createPriceLine` on the series, same pattern as Fibonacci tool)
  - Unit tests in `frontend/tests/unit/indicators.test.ts` for each new function
  - Backend Python equivalents added to `backend/app/services/indicators/`
- **Complexity:** M
- **Dependencies:** ST-V (establishes indicator extension pattern)

### ST-X · Drawing Tools — Pitchfork + Annotation
- **Source:** `PLATFORM_STATUS.md:764`, `trading-platform-plan.md`
- **Current state:** `useFibonacciTool.ts` and `useTrendlineTool.ts` are complete and wired. Missing: Andrews' Pitchfork, free-text Annotation. (Gann Fan and Elliott Wave are Tier 2.)
- **Acceptance criteria:**
  - `usePitchforkTool.ts` — 3-click interaction: median line + two parallel lines; render as 3 `LineSeries`; persist in `chartStore.drawings.pitchfork`
  - `useAnnotationTool.ts` — single-click to place a text label at price level; label content editable via prompt or inline input; rendered as a `createPriceLine` with title; persist in `chartStore.drawings.annotations`
  - Both tools wired into `ChartToolbar.tsx` (following existing Fib/Trend pattern) and `ChartPanel/index.tsx`
  - `ChartStoreDrawings` type extended with `pitchfork` and `annotations` arrays
  - ≥ 2 unit tests each (hook instantiates without error; activate/deactivate state transitions correctly)
- **Complexity:** M
- **Dependencies:** ST-21 / ST-22 (existing drawing tool infrastructure)

### ST-Y · AIScorePanel
- **Source:** `trading-platform-plan.md:324`
- **Current state:** `frontend/components/panels/AIScorePanel/` does not exist. No backend endpoint for aggregated AI score exists.
- **Acceptance criteria:**
  - `frontend/components/panels/AIScorePanel/index.tsx` renders: overall AI confidence score (0–100 gauge), sentiment timeline chart (last 30 days), signal label (Bullish/Neutral/Bearish), reasoning summary text
  - `GET /api/v1/ml/ai-score?ticker=X` endpoint aggregates: FinBERT sentiment score, LSTM prediction probability, XGBoost signal probability → weighted composite score
  - Panel registered in `frontend/app/page.tsx` panel registry (24th panel slot)
  - `backend/tests/unit/test_ml.py` — 2 tests: endpoint returns score in [0,100] range; returns 503 gracefully when no model is trained
  - Frontend panel mock-renders correctly in `panels_new.test.tsx`
- **Complexity:** L
- **Dependencies:** ST-16 (LSTM), ST-17 (XGBoost) — both complete per current sprint

### ST-Z · BacktestPanel Sub-Components
- **Source:** `trading-platform-plan.md`, `platform-completion-plan.md`
- **Current state:** `frontend/components/panels/BacktestPanel/index.tsx` renders equity curve inline using lightweight-charts with no sub-component extraction. No `MonthlyReturnsHeatmap`, `EquityCurveChart`, or `DrawdownChart` components exist.
- **Acceptance criteria:**
  - `frontend/components/panels/BacktestPanel/EquityCurveChart.tsx` — extracted equity curve chart component accepting `equity_curve: number[]` + `timestamps: string[]` props
  - `frontend/components/panels/BacktestPanel/DrawdownChart.tsx` — drawdown time-series chart (derived from equity curve) as a separate component
  - `frontend/components/panels/BacktestPanel/MonthlyReturnsHeatmap.tsx` — calendar heatmap of monthly returns; rows=years, columns=months; cells colored green/red proportional to return; uses SVG or a lightweight grid
  - `frontend/components/panels/BacktestPanel/index.tsx` imports and uses all three sub-components
  - Each sub-component has ≥ 1 Vitest unit test (renders without crashing with mock data)
- **Complexity:** M
- **Dependencies:** None (pure frontend refactor)

---

## 4. Tier 2 — Medium Priority

### ST-I · Volume Profile / VPVR
- **Source:** `PLATFORM_STATUS.md:774`, `next-sprint-plan.md`
- **Current state:** `GET /market/vpvr/{symbol}` exists in `market.py`. The `ChartCanvas.tsx` has a VPVR canvas overlay renderer (right-side histogram). However, the VPVR panel does not appear to be wired into a dedicated panel; it is only available if `vpvr` prop is passed to `ChartCanvas`.
- **Acceptance criteria:**
  - VPVR data is fetched automatically when `ChartPanel` loads, using the same symbol/timeframe as the main chart
  - The `vpvr` prop is passed from `ChartPanel/index.tsx` to `ChartCanvas` using a `useEffect`-triggered fetch to `GET /market/vpvr/{symbol}`
  - Loading state handled gracefully (no VPVR shown while fetching)
  - `backend/tests/unit/test_market.py` has a test for the VPVR endpoint
- **Complexity:** S
- **Dependencies:** None (backend endpoint and canvas renderer already exist)

### ST-AA · Screener Presets DB Persistence
- **Source:** `trading-platform-plan.md:977`, `backend/app/api/v1/screener.py`
- **Current state:** `POST /screener/presets` accepts JSON but returns a note: "User preset persistence requires PostgreSQL integration." Presets are hardcoded in-memory only.
- **Acceptance criteria:**
  - `ScreenerPreset` SQLAlchemy model: `id` (UUID PK), `user_id` (FK → users), `name` (String), `conditions` (JSON), `created_at`
  - Alembic migration `0004_add_screener_presets.py` (reversible)
  - `POST /screener/presets` saves to DB; `GET /screener/presets` returns built-in presets merged with user's saved presets; `DELETE /screener/presets/{id}` removes a user preset
  - 3 unit tests: create preset, list (built-ins + user), delete
- **Complexity:** S
- **Dependencies:** None

### ST-AB · News Adapters — Reddit + SEC EDGAR
- **Source:** `trading-platform-plan.md:488-498`, `PLATFORM_STATUS.md:311`
- **Current state:** `backend/app/services/news/` has `aggregator.py`, `benzinga.py`, `newsapi.py`. Reddit, SEC EDGAR, and Twitter adapters are absent.
- **Acceptance criteria:**
  - `backend/app/services/news/reddit.py` — `RedditAdapter` using PRAW; fetches posts from `r/stocks`, `r/wallstreetbets`, `r/investing` for a given ticker; rate-limited; graceful fallback when `REDDIT_CLIENT_ID` absent
  - `backend/app/services/news/sec_edgar.py` — `SECEdgarAdapter`; fetches recent 8-K and 10-Q filings for a ticker via SEC EDGAR REST API (no API key required); extracts filing date, form type, URL
  - Both adapters registered in `news/aggregator.py` alongside existing providers
  - `GET /news/{symbol}` response includes `source` field distinguishing newsapi/benzinga/reddit/sec items
  - 2 unit tests per adapter: mocked happy path + missing credentials fallback
  - Twitter/X adapter deferred to Tier 3 (rate limits and cost are prohibitive on free tier)
- **Complexity:** M
- **Dependencies:** None

### ST-AC · Indicator Library — Extended Set (Ichimoku, Stoch-RSI, SuperTrend)
- **Source:** `trading-platform-plan.md:344-383`
- **Current state:** Not present in `frontend/lib/indicators/index.ts`
- **Acceptance criteria:**
  - `frontend/lib/indicators/index.ts` exports `ichimokuCloud` (tenkan, kijun, senkouA, senkouB, chikou), `stochasticRsi` (already in ST-V — ensure not duplicated), `superTrend` (ATR-based trend with direction), `roc` (Rate of Change), `ultimateOscillator`, `trix`
  - Ichimoku rendered as 5 overlapping line series + cloud fill (shaded area between senkouA and senkouB) in `ChartCanvas.tsx`
  - All new indicators appear in `INDICATOR_TYPES` dropdown in `ChartToolbar.tsx`
  - Unit tests for each function
- **Complexity:** L
- **Dependencies:** ST-V (momentum indicators already added, pattern established)

### ST-AD · order_book_snapshots Hypertable
- **Source:** `trading-platform-plan.md:728`
- **Current state:** The TimescaleDB schema (per `docs/architecture/database-schema.md`) has `ohlcv` and `ticks` hypertables. `order_book_snapshots` is specified in the original schema but absent.
- **Acceptance criteria:**
  - Alembic migration `0005_add_order_book_snapshots.py` creates `order_book_snapshots` TimescaleDB hypertable: `(time TIMESTAMPTZ, symbol TEXT, bids JSONB, asks JSONB, mid_price NUMERIC, spread NUMERIC)` with time as partitioning column, 1-day chunks
  - `record_order_book_snapshot` Celery task in `backend/app/tasks/data_tasks.py` reads from Alpaca WebSocket order book feed and writes batched snapshots
  - `docs/architecture/database-schema.md` updated to include the new table
  - Migration is reversible (downgrade drops hypertable)
- **Complexity:** M
- **Dependencies:** ST-5 (record_ticks pattern established — follow same batching approach)

### ST-AE · Market Snapshot Endpoint Enrichment
- **Source:** `trading-platform-plan.md:944`
- **Current state:** `GET /market/snapshot/{symbol}` exists in `market.py` and returns `{symbol, quote, timestamp}`. The original spec called for quote + fundamentals + sentiment bundle.
- **Acceptance criteria:**
  - Response extended to include: `quote` (existing), `fundamentals` (P/E, market cap, 52w high/low — from yfinance `Ticker.info`), `sentiment` (latest FinBERT score from `sentiment/` service), `latest_news` (first 3 headlines from news aggregator)
  - All three enrichment fields degrade gracefully (omitted from response if provider unavailable, not 500)
  - `backend/tests/unit/test_market.py` — test that snapshot returns valid structure with mocked providers
- **Complexity:** M
- **Dependencies:** None (yfinance already integrated; sentiment pipeline complete)

### ST-R · Real-Time Indicator Streaming (SSE)
- **Source:** `next-sprint-plan.md`
- **Current state:** Indicators are computed client-side in `frontend/lib/indicators/index.ts`. No server-sent indicator stream exists.
- **Acceptance criteria:**
  - `GET /market/indicators/stream/{symbol}?indicators=sma_20,rsi_14,macd` — Server-Sent Events endpoint
  - Backend computes indicators on each new bar or tick, sends SSE event: `{time, symbol, indicator_id, value}`
  - Frontend `useIndicatorStream` hook in `frontend/hooks/useIndicatorStream.ts` subscribes and updates `chartStore` in real time
  - Existing client-side computation remains as fallback (no regression)
  - 2 backend unit tests: SSE stream opens and sends data; disconnects cleanly on client close
- **Complexity:** L
- **Dependencies:** None

### ST-S · Portfolio Import (CSV + Broker OAuth)
- **Source:** `next-sprint-plan.md`
- **Current state:** `backend/app/api/v1/portfolio.py` has a CSV import endpoint. The CSV validation is complete (3 tests pass). Broker OAuth is not implemented.
- **Acceptance criteria:**
  - `POST /portfolio/import/csv` — already exists; add position deduplication (update quantity if symbol already in portfolio, don't insert duplicate)
  - `POST /portfolio/import/broker` — stub endpoint returning `{"status": "not_implemented", "message": "Broker OAuth requires production API credentials"}` with 501 status code (prevents silent 404 on future integration)
  - Frontend `PortfolioPanel` shows an "Import CSV" button that opens a file picker and POSTs to the existing endpoint
  - If file picker is already present, ensure the response error states (invalid CSV, duplicate) are displayed to the user
- **Complexity:** S
- **Dependencies:** None

### ST-T · Multi-User Workspace Mode (UI Tier)
- **Source:** `next-sprint-plan.md`, sub-tasks 1b (backend complete)
- **Current state:** `Workspace` and `WorkspaceMember` ORM models, DB-backed CRUD, and RBAC are complete in `backend/app/api/v1/workspaces.py`. The frontend has no workspace switcher UI — users cannot create, switch, or share workspaces from the dashboard.
- **Acceptance criteria:**
  - `WorkspaceSwitcher` React component in `frontend/components/layout/WorkspaceSwitcher.tsx`: dropdown showing user's workspaces (owner + member); "New workspace" button; "Invite member" dialog (email + role)
  - `WorkspaceSwitcher` mounted in the dashboard navbar
  - Active workspace ID stored in `useLayoutStore`; when switched, the layout store loads the saved workspace `layout` JSON from `GET /api/v1/workspaces/{id}`
  - Workspace layout auto-saves to `PATCH /api/v1/workspaces/{id}` when `setLayout` is called (debounced 2s)
  - 3 frontend unit tests: switcher renders workspace list; invite dialog opens; selecting a workspace dispatches layout update
- **Complexity:** M
- **Dependencies:** Sub-tasks 1b (workspace backend — complete)

### ST-U · Tick Data Recorder + Replay
- **Source:** `next-sprint-plan.md`, sub-task 5 (record_ticks complete)
- **Current state:** `_TickBatcher` in `backend/app/tasks/data_tasks.py` is implemented with 500-tick/1s batching and writes to the `ticks` hypertable. The tick replay engine in `backtesting/` has the tick replay executor. However, no API endpoint exposes recorded tick data for replay, and there is no connection between the stored ticks and the backtesting tick replay engine.
- **Acceptance criteria:**
  - `GET /market/ticks/{symbol}?start=&end=&limit=` — returns recorded ticks from the `ticks` hypertable for a symbol + time range
  - Backtesting `tick_replay.py` engine accepts a `data_source="db"` argument that queries tick data from TimescaleDB instead of from file
  - `POST /backtests/run` accepts `engine="tick_replay"` and `data_source="db"` parameters
  - Integration test: runs tick replay backtest on 100 rows of synthetic tick data inserted directly into the test DB
- **Complexity:** M
- **Dependencies:** Sub-task 5 (record_ticks — complete)

---

## 5. Tier 3 — Low Priority / Infrastructure

### ST-N · Load Tests (k6) — CI Integration
- **Source:** `PLATFORM_STATUS.md:782`, `next-sprint-plan.md`
- **Current state:** `tests/load/rest_auth.js` and `ws_market.js` exist as real k6 scripts targeting 1,000 concurrent VUs with p99 < 100ms. They are NOT run in CI — `.github/workflows/ci.yml` has no k6 job.
- **Acceptance criteria:**
  - A new CI job `load-test` added to `.github/workflows/ci.yml` (gated on `workflow_dispatch` or schedule — not on every PR, to avoid cost)
  - Job spins up the Docker Compose stack, waits for health checks, runs `k6 run tests/load/ws_market.js`, asserts exit code 0
  - `docs/developer/load-testing.md` updated with local run instructions and pass/fail thresholds
- **Complexity:** S
- **Dependencies:** COMP-21 (CI secrets needed to run backend)

### ST-AF · Architecture Documentation Completion
- **Source:** `PLATFORM_STATUS.md:785`, `trading-platform-plan.md`
- **Current state:** `docs/developer/` has `deployment.md` and `load-testing.md`. `docs/architecture/` has `database-schema.md`. Missing: `system-overview.md`, `data-flow.md`, `api-contract.md`, `adding-indicators.md`, `adding-data-providers.md`.
- **Acceptance criteria:**
  - `docs/architecture/system-overview.md` — ASCII diagram of service topology (browser → nginx → backend/frontend → TimescaleDB/Redis/MongoDB/Celery) plus component responsibility table
  - `docs/architecture/data-flow.md` — step-by-step narrative of: (a) market data ingestion path, (b) backtest execution path, (c) alert evaluation path; includes sequence diagrams (Mermaid)
  - `docs/architecture/api-contract.md` — table of all 18 route files, their prefixes, auth requirements, and a 1-line description per endpoint group
  - `docs/developer/adding-indicators.md` — step-by-step guide for adding a new indicator to the frontend library and wiring it into ChartToolbar
  - `docs/developer/adding-data-providers.md` — step-by-step guide for adding a new market data adapter (implement `base.py` ABC, register in `router.py`, add env var to `config.py`)
- **Complexity:** S
- **Dependencies:** None

### ST-AG · Chart Types — Renko + Line Break
- **Source:** `trading-platform-plan.md:1337`
- **Current state:** `ChartCanvas.tsx` supports: `candlestick`, `heikin_ashi`, `bar`, `line`, `area`, `baseline`. Renko, Line Break, Point & Figure, and Kagi are absent. (P&F and Kagi are Tier 4 given their complexity.)
- **Acceptance criteria:**
  - `renko` chart type added: user-configurable brick size; OHLCV bars transformed server-side at `GET /market/bars/{symbol}?chart_type=renko&brick_size=1.0`; rendered as `BarSeries` in lightweight-charts
  - `line_break` chart type added: N-line break (default 3); transformation server-side; rendered as `BarSeries`
  - Both chart types appear in `CHART_TYPES` in `ChartToolbar.tsx`
  - `ChartType` type union in `chartStore.ts` extended
  - Unit tests: renko transform produces correct brick count from known price sequence; line break transform produces correct break sequence
- **Complexity:** M
- **Dependencies:** None

### ST-AH · Transformer Model ADR Expansion
- **Source:** `platform-completion-plan.md` sub-task 18 (complete — ADR-005 exists)
- **Current state:** `docs/adr/ADR-005-transformer-deferral.md` created. README ML section updated.
- **Acceptance criteria (refinement):**
  - ADR-005 includes a concrete re-engagement checklist: minimum LSTM/XGBoost performance benchmarks that must be exceeded before transformer investment is justified
  - `docs/adr/` contains ADR-006 through ADR-008 for the three major architecture decisions made during the completion sprint (DB-backed strategies, WeasyPrint PDF, PyTorch LSTM)
  - ADR index in `docs/adr/README.md` updated
- **Complexity:** S
- **Dependencies:** Sub-task 18 (complete)

### ST-AI · K8s Manifests — Completeness Audit
- **Source:** `next-sprint-plan.md` ST-P, `infra/k8s/`
- **Current state:** 7 K8s manifests exist. Missing: TimescaleDB StatefulSet, MongoDB StatefulSet, Prometheus + Grafana deployments, HorizontalPodAutoscaler for backend/celery, PersistentVolumeClaims for databases.
- **Acceptance criteria:**
  - `infra/k8s/timescaledb.yaml` — StatefulSet + Service + PVC
  - `infra/k8s/mongodb.yaml` — StatefulSet + Service + PVC
  - `infra/k8s/monitoring.yaml` — Prometheus Deployment + Grafana Deployment (reusing configs from `infra/monitoring/`)
  - `infra/k8s/hpa.yaml` — HPA for backend (min 2, max 10, CPU 70%) and celery_worker (min 1, max 5)
  - `docs/developer/deployment.md` updated with `kubectl apply -f infra/k8s/` instructions
  - All manifests use `quantnexus` namespace (matches `namespace.yaml`)
- **Complexity:** M
- **Dependencies:** None

### ST-AJ · Terraform ECS — Variable Completion
- **Source:** `trading-platform-plan.md:640`, `infra/terraform/`
- **Current state:** `infra/terraform/` has `main.tf`, `ecs.tf`, `alb.tf`, `variables.tf`, `outputs.tf`. The variables file likely has placeholders for VPC ID, subnet IDs, and ECR image URIs.
- **Acceptance criteria:**
  - `infra/terraform/variables.tf` has no `default = ""` or `default = null` for required variables that have no sensible default — each must have a `description` and the CI pipeline validates `terraform validate` passes
  - `infra/terraform/README.md` documents all required variables, how to set them, and the deployment sequence
  - `terraform validate` added as a CI step (syntax check only, no `plan` or `apply`)
- **Complexity:** S
- **Dependencies:** None

---

## 6. Tier 4 — Long Horizon / Explicitly Deferred

### DEFER-1 · C++ Execution Engine / OMS
- **Source:** `trading-platform-plan.md:43,629`
- **Current state:** `engine/` directory completely empty
- **Rationale for deferral:** Requires dedicated systems engineering work (C++17/20, FIX protocol library integration, low-latency network programming). Not meaningful without live brokerage connectivity. Python paper trading via Alpaca covers all demo-mode requirements.
- **Re-engagement criteria:** Platform has live brokerage connectivity (DEFER-3); sustained daily active users > 100; latency benchmarking shows Python order dispatch is a bottleneck
- **Complexity:** XL
- **Dependencies:** DEFER-3

### DEFER-2 · FIX Protocol Integration
- **Source:** `trading-platform-plan.md:44`
- **Current state:** Nothing exists
- **Rationale:** Requires institutional brokerage relationships and compliance review
- **Complexity:** XL
- **Dependencies:** DEFER-1, DEFER-3

### DEFER-3 · Live Order Routing (Real Brokerage)
- **Source:** `trading-platform-plan.md:45`
- **Current state:** Only Alpaca paper trading. Config keys `OANDA_API_KEY` and `OANDA_ACCOUNT_ID` exist in `config.py` but no OANDA adapter is implemented.
- **Re-engagement criteria:** Legal review complete; risk management layer (position limits, kill switch) in place; at least one of DEFER-1 or a Python-native smart order router implemented
- **Complexity:** XL
- **Dependencies:** None (technically), but ST-J (advanced orders) must be complete

### DEFER-4 · Point & Figure + Kagi Chart Types
- **Source:** `trading-platform-plan.md:1337`
- **Rationale:** These chart types require fundamentally different data structures (no time axis) that are incompatible with lightweight-charts `TimeScale`. Would require a custom canvas renderer. Deferred until demand is demonstrated.
- **Complexity:** L
- **Dependencies:** ST-AG (Renko/Line Break pattern)

### DEFER-5 · Gann Fan + Elliott Wave Drawing Tools
- **Source:** `PLATFORM_STATUS.md:764`, `trading-platform-plan.md`
- **Rationale:** Elliott Wave requires automated wave detection or complex manual labeling UI. Gann Fan requires angle-based projections. Both are specialist tools with niche demand. Deferred after Pitchfork (ST-X) is shipped.
- **Complexity:** L
- **Dependencies:** ST-X (Pitchfork establishes multi-point drawing pattern)

### DEFER-6 · Twitter/X News Adapter
- **Source:** `trading-platform-plan.md:488-498`
- **Rationale:** Twitter/X API v2 Basic tier costs $100/month and imposes strict rate limits on financial data use. Free tier has been eliminated. Deferred pending cost/benefit review.
- **Complexity:** S
- **Dependencies:** ST-AB (other news adapters complete first)

### DEFER-7 · Seeking Alpha Adapter
- **Source:** `trading-platform-plan.md`
- **Rationale:** No public API; scraping violates ToS. Requires a paid data vendor agreement.
- **Complexity:** M
- **Dependencies:** None

### DEFER-8 · ML Training Pipeline (ml/training/, ml/experiments/, ml/feature_store/)
- **Source:** `trading-platform-plan.md:46`
- **Current state:** `ml/training/`, `ml/experiments/`, `ml/feature_store/`, `ml/serving/` directories exist but are empty
- **Rationale:** LSTM and XGBoost training via Celery tasks covers the immediate ML needs. A full MLOps pipeline (experiment tracking, feature store, model registry) is premature until model performance baselines are established.
- **Re-engagement criteria:** LSTM and XGBoost models are actively used with >1000 inference calls/day; model drift is observable; A/B testing between model versions is needed
- **Complexity:** XL
- **Dependencies:** ST-16, ST-17 (models complete — already done)

---

## 7. Dependency Graph (Tier 0 + Tier 1)

```
COMP-21 (CI Live-Data Secrets)
    │
    └──► COMP-22 (E2E with Live Credentials)

ST-16/17 (LSTM/XGBoost — COMPLETE)
    │
    └──► ST-Y (AIScorePanel)
             │
             └──► [Tier 2: ST-R Real-Time Indicator Streaming]

Sub-task 1b (Workspace Backend — COMPLETE)
    │
    └──► ST-T (Multi-User Workspace UI)

Sub-tasks 21/22 (Drawing Tool Wiring — COMPLETE)
    │
    └──► ST-X (Pitchfork + Annotation)
             │
             └──► [Tier 4: DEFER-5 Gann/Elliott Wave]

ST-V (Momentum+Trend Indicators)
    │
    └──► ST-W (Volume+Structure Indicators)
             │
             └──► ST-AC (Extended Set: Ichimoku, SuperTrend)

Sub-task 5 (record_ticks — COMPLETE)
    │
    └──► ST-AD (order_book_snapshots Hypertable)
    └──► ST-U (Tick Replay from DB)

[No upstream deps]:
    ST-J (Advanced Orders)
    ST-Q (Regime Detection HMM)
    ST-Z (BacktestPanel Sub-Components)
    ST-I (VPVR wiring)
    ST-AA (Screener Presets DB)
    ST-AB (Reddit/SEC News)
    ST-AE (Snapshot Enrichment)
```

---

## 8. Recommended Execution Order

Each sprint targets a coherent scope. Dependency order is respected.

### Sprint 1 — CI & Test Completeness
Items: COMP-21, COMP-22, ST-N (k6 CI integration)  
Goal: All tests (unit + E2E + load) run reliably in CI with real credentials.

### Sprint 2 — Core Feature Gaps (Orders + Indicators I)
Items: ST-J (Advanced Orders), ST-V (Momentum+Trend Indicators), ST-I (VPVR auto-fetch)  
Goal: Trading workflow complete; chart panel gains 6 new indicator overlays; VPVR auto-loads.

### Sprint 3 — AI Features
Items: ST-Q (Regime HMM endpoints), ST-Y (AIScorePanel), ST-Z (BacktestPanel sub-components)  
Goal: ML models surfaced in the UI; backtest results presentation complete.

### Sprint 4 — Drawing Tools + Volume Indicators
Items: ST-X (Pitchfork + Annotation), ST-W (Volume+Structure Indicators)  
Goal: All Tier 1 drawing tools shipped; indicator library covers original spec for volume/structure.

### Sprint 5 — Data Enrichment
Items: ST-AA (Screener Presets DB), ST-AB (Reddit + SEC EDGAR news), ST-AE (Snapshot Enrichment), ST-S (Portfolio Import fixes)  
Goal: Screener and market snapshot return richer data; news aggregates from 4 sources.

### Sprint 6 — Multi-User + Tick Data
Items: ST-T (Workspace UI), ST-U (Tick Replay from DB), ST-AD (order_book_snapshots hypertable)  
Goal: Workspace switching works in the UI; tick data pipeline fully connected to backtesting.

### Sprint 7 — Extended Indicators + Chart Types
Items: ST-AC (Ichimoku, SuperTrend, TRIX), ST-AG (Renko, Line Break chart types), ST-R (SSE Indicator Streaming)  
Goal: Indicator library reaches original spec coverage; chart types expanded.

### Sprint 8 — Infrastructure + Docs
Items: ST-AI (K8s completeness), ST-AJ (Terraform), ST-AH (ADR expansion), ST-AF (Docs)  
Goal: Infrastructure is production-ready; developer onboarding documentation complete.

---

## 9. Summary Table

| ID | Tier | Title | Complexity | Status |
|---|---|---|---|---|
| COMP-21 | 0 | CI Live-Data Secrets | S | Pending |
| COMP-22 | 0 | E2E Tests with Live Credentials | M | Pending |
| ST-J | 1 | Advanced Order Features | M | Pending |
| ST-Q | 1 | Regime Detection HMM (endpoints + UI) | M | Pending |
| ST-V | 1 | Indicator Library — Momentum + Trend | M | Pending |
| ST-W | 1 | Indicator Library — Volume + Structure | M | Pending |
| ST-X | 1 | Drawing Tools — Pitchfork + Annotation | M | Pending |
| ST-Y | 1 | AIScorePanel | L | Pending |
| ST-Z | 1 | BacktestPanel Sub-Components | M | Pending |
| ST-I | 2 | VPVR Auto-Fetch Wiring | S | Pending |
| ST-R | 2 | Real-Time Indicator Streaming (SSE) | L | Pending |
| ST-S | 2 | Portfolio Import (dedup + broker stub) | S | Pending |
| ST-T | 2 | Multi-User Workspace UI | M | Pending |
| ST-U | 2 | Tick Data Recorder + Replay | M | Pending |
| ST-AA | 2 | Screener Presets DB Persistence | S | Pending |
| ST-AB | 2 | News Adapters — Reddit + SEC EDGAR | M | Pending |
| ST-AC | 2 | Indicator Library — Extended (Ichimoku, SuperTrend) | L | Pending |
| ST-AD | 2 | order_book_snapshots Hypertable | M | Pending |
| ST-AE | 2 | Market Snapshot Enrichment | M | Pending |
| ST-N | 3 | Load Tests — CI Integration | S | Pending |
| ST-AF | 3 | Architecture Documentation | S | Pending |
| ST-AG | 3 | Chart Types — Renko + Line Break | M | Pending |
| ST-AH | 3 | ADR Expansion (ADR-006/007/008) | S | Pending |
| ST-AI | 3 | K8s Manifests Completeness Audit | M | Pending |
| ST-AJ | 3 | Terraform Variable Completion | S | Pending |
| DEFER-1 | 4 | C++ Execution Engine / OMS | XL | Deferred |
| DEFER-2 | 4 | FIX Protocol Integration | XL | Deferred |
| DEFER-3 | 4 | Live Order Routing (Real Brokerage) | XL | Deferred |
| DEFER-4 | 4 | Point & Figure + Kagi Chart Types | L | Deferred |
| DEFER-5 | 4 | Gann Fan + Elliott Wave Drawing Tools | L | Deferred |
| DEFER-6 | 4 | Twitter/X News Adapter | S | Deferred |
| DEFER-7 | 4 | Seeking Alpha Adapter | M | Deferred |
| DEFER-8 | 4 | ML Training Pipeline (MLOps) | XL | Deferred |

---

## 10. Completed Items (Baseline Reference)

The following items from prior sprint plans are **complete** as of the current baseline:

| ID | Title |
|---|---|
| COMP-1 | StrategyConfig ORM model + migration + DB-backed strategies |
| COMP-2 | Workspace + WorkspaceMember ORM + DB-backed workspaces |
| COMP-3 | Alert ORM wired + evaluate_alerts Celery task |
| COMP-4 | refresh_ohlcv Celery task (full implementation) |
| COMP-5 | record_ticks + _TickBatcher |
| COMP-6 | Polygon.io options adapter |
| COMP-7 | CoinGecko crypto adapter |
| COMP-8 | Binance crypto adapter |
| COMP-9 | FRED macro adapter with Redis caching |
| COMP-10 | GridSearchOptimizer standalone class |
| COMP-11 | PDF report generator + /backtests/{run_id}/report/pdf endpoint |
| COMP-12 | Playwright E2E auth.spec.ts (POM, 6 tests) |
| COMP-13 | Playwright E2E trading.spec.ts |
| COMP-14 | Playwright E2E backtesting.spec.ts |
| COMP-15 | Playwright E2E watchlist.spec.ts |
| COMP-16 | LSTM price prediction model (PyTorch) + train/predict endpoints |
| COMP-17 | XGBoost signal classifier + train/predict/features endpoints |
| COMP-18 | Transformer ADR-005 + README ML section |
| COMP-19 | useFibonacciTool.ts hook |
| COMP-20 | useTrendlineTool.ts hook |
| COMP-21 | ChartToolbar drawing tool buttons wired (Fib + Trend) |
| COMP-22 | ChartPanel/index.tsx hooks + workspace persist wired |
| COMP-23 | Backend Dockerfile WeasyPrint + libgomp system deps |
| COMP-24 | Docker Compose ml_weights named volume |
| COMP-25 | JSONB/ARRAY/UUID model portability (SQLite test compat) |
| ST-A | Alembic Migration + Portfolio/Trades (initial schema) |
| ST-B | Celery Order-Polling |
| ST-C | Indicator Overlay System (ChartCanvas) |
| ST-D | BacktestPanel Frontend (base implementation) |
| ST-E | Additional Backtesting Strategies |
| ST-F | Ticker Sparklines |
| ST-G | WebSocket Resilience (exponential backoff) |
| ST-H | Volatility Surface Panel |
| ST-K | Bayesian Optimization (Optuna) |
| ST-L | Strategy Builder UI (ReactFlow) |
| ST-M | AI Trade Journal |
| ST-O | Architecture Decision Records (ADR-001 to ADR-004) |
