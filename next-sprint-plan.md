# QuantNexus — Next Sprint Plan

Covers every item in §13 (Outstanding Work) and §14 (New Ideas) of `PLATFORM_STATUS.md`,
broken into independently implementable sub-tasks in priority order.

Items that cannot run without a real PostgreSQL or external credentials (13.4, 13.5) are
scoped as wiring-only tasks — no live secrets are hardcoded.

---

## Table of Contents

- [ST-A: Alembic Migration + Portfolio/Trades Endpoint](#st-a)
- [ST-B: Celery Order-Polling Task](#st-b)
- [ST-C: Indicator Overlay System (ChartCanvas)](#st-c)
- [ST-D: BacktestPanel Frontend](#st-d)
- [ST-E: Additional Backtesting Strategies](#st-e)
- [ST-F: Ticker Sparklines in WatchlistPanel](#st-f)
- [ST-G: WebSocket Resilience (Exponential Backoff)](#st-g)
- [ST-H: Volatility Surface Panel (VolatilityPanel)](#st-h)
- [ST-I: Volume Profile (VPVR)](#st-i)
- [ST-J: Advanced Order Features (Bracket / OCO / Modify)](#st-j)
- [ST-K: Bayesian Optimization (Optuna)](#st-k)
- [ST-L: Strategy Builder UI](#st-l)
- [ST-M: AI Trade Journal](#st-m)
- [ST-N: Load Tests (k6)](#st-n)
- [ST-O: Architecture Decision Records (ADRs)](#st-o)
- [ST-P: Kubernetes Manifests + Terraform IaC](#st-p)
- [ST-Q: Regime Detection (HMM)](#st-q)
- [ST-R: Real-Time Indicator Streaming (SSE)](#st-r)
- [ST-S: Portfolio Import (CSV + Broker OAuth)](#st-s)
- [ST-T: Multi-User & Workspace Mode](#st-t)
- [ST-U: Tick Data Recorder + Replay](#st-u)

---

## Validation contract (must stay green after every ST)

```
ruff check ✅   ruff format ✅   bandit -ll ✅ (0 H/M/L)
eslint --max-warnings=0 ✅   tsc --noEmit ✅
pytest 64/64 ✅ (2 skipped = migration tests need real PG)
backtesting/tests 33/33 ✅
vitest (all unit) ✅   next build ✅
```

Any ST that adds backend files must run pytest.
Any ST that adds frontend files must run vitest + next build.
New test files must not break existing counts.

---

## ST-A — Alembic Migration + Portfolio/Trades Endpoint  [ ] pending

### Intent
The `Order` SQLAlchemy model exists but is not imported into `app/models/__init__.py` or
`migrations/env.py`, so the `orders` table is never created by Alembic autogenerate.
`PerformancePanel` calls `GET /api/v1/portfolio/trades` which does not exist — it falls
back to demo data silently. This ST fixes both gaps.

### Expected Outcomes
- `Order` is included in Alembic autogenerate; a new migration file is generated covering
  the `orders` table with all columns from `app/models/order.py`.
- `GET /api/v1/portfolio/trades` returns filled orders as `TradeRecord[]`; falls back to
  an empty list when no filled orders exist.
- `pytest` still passes (the 2 migration-test skips remain skipped without real PG).
- `ruff check` + `bandit -ll` clean.

### Todo List
1. Add `from app.models.order import Order` to `backend/app/models/__init__.py` and
   include `Order` in `__all__`.
2. Add `order` to the `from app.models import (...)` import in `backend/migrations/env.py`
   so autogenerate picks it up.
3. Generate the migration:
   ```bash
   cd backend && /Users/henrynguyen/.local/bin/uv run alembic revision \
     --autogenerate -m "add_orders_table"
   ```
   Review the generated file to confirm `orders` table columns match `order.py`.
4. Add `GET /portfolio/trades` to `backend/app/api/v1/portfolio.py`:
   - Route path: `/trades`
   - Query: select `Order` rows where `user_id == current_user["sub"]` and
     `status == "filled"`, ordered by `filled_at desc`, with a default `limit=200`.
   - Return a list of dicts with keys matching `TradeRecord` in `PerformancePanel`:
     `id, symbol, side, quantity, entry_price (filled_avg_price), exit_price (None for now),
     entry_time (submitted_at), exit_time (filled_at), pnl (None), pnl_pct (None)`.
   - Falls back to `[]` when the table is empty (no real database needed for unit test).
5. Add a unit test in `backend/tests/unit/test_orders.py` (or a new file) that calls
   the route with a mock DB session and asserts the response shape.
6. Run validation: `ruff check`, `bandit -ll`, `pytest`.

### Relevant Context
- `backend/app/models/order.py` — Order model definition
- `backend/app/models/__init__.py` — needs `Order` import (currently missing)
- `backend/migrations/env.py` lines 14-24 — module-level imports for autogenerate
- `backend/app/api/v1/portfolio.py` — add new route here
- `frontend/components/panels/PerformancePanel/index.tsx` — calls `/api/v1/portfolio/trades`,
  expects `TradeRecord[]` with `{id, symbol, side, quantity, entry_price, pnl, pnl_pct, entry_time}`
- `backend/app/dependencies.py` — `CurrentUser`, `DBSession` injection pattern

---

## ST-B — Celery Order-Polling Task  [ ] pending

### Intent
`orders_feed.py` has `publish_order_update()` but nothing ever calls it, so the
`/ws/orders` WebSocket is permanently silent after an order is placed. A Celery
periodic task needs to poll Alpaca for open order status, detect fills/cancellations,
update the DB record, and publish to the Redis channel. When Alpaca keys are absent
the task is a no-op (demo mode).

### Expected Outcomes
- `backend/app/tasks/order_tasks.py` exists with a `sync_open_orders` Celery task.
- The task is registered in `celery_app.py`'s `include` list and has a beat schedule
  entry (every 10 seconds).
- When Alpaca keys are present: polls `GET /v2/orders?status=open`, updates `status`,
  `filled_qty`, `filled_avg_price`, `filled_at` in PostgreSQL, then calls
  `publish_order_update()` for each changed order.
- When Alpaca keys are absent: task logs a debug message and exits immediately.
- Unit test in `backend/tests/unit/test_orders.py`: mock Alpaca HTTP → assert
  `publish_order_update` called with correct payload.
- `ruff`, `bandit`, `pytest` clean.

### Todo List
1. Create `backend/app/tasks/order_tasks.py`:
   - Import `celery_app`, `get_settings`, `httpx`, `asyncio`, `publish_order_update`.
   - `@celery_app.task(name="order_tasks.sync_open_orders")` — synchronous Celery task
     that runs an inner `async` function via `asyncio.run()` (Celery workers are sync
     by default; event loop is created per-task invocation).
   - Inner async: check `_is_alpaca_available()`; if not, return early.
   - GET `https://paper-api.alpaca.markets/v2/orders?status=open` with Alpaca key headers.
   - For each returned order: look up DB record by `broker_order_id`; if `status` changed,
     update record and call `publish_order_update(user_id, order_data)`.
   - All DB access via `async_session_factory` directly (no FastAPI dependency injection
     — this is a Celery worker context).
2. Add `"app.tasks.order_tasks"` to the `include` list in `celery_app.py`.
3. Add beat schedule to `celery_app.py`:
   ```python
   celery_app.conf.beat_schedule = {
       "sync-open-orders-every-10s": {
           "task": "order_tasks.sync_open_orders",
           "schedule": 10.0,
       },
   }
   ```
4. Add unit test: mock `httpx.AsyncClient.get` to return a filled-order JSON payload;
   mock `publish_order_update`; assert it is called with the right `user_id` and
   `order_data` keys.
5. Run `ruff check`, `bandit -ll`, `pytest`.

### Relevant Context
- `backend/app/api/ws/orders_feed.py` — `publish_order_update(user_id, order_data)` async
- `backend/app/services/orders/service.py` — `_is_alpaca_available()`, `_parse_alpaca_order()`
- `backend/app/tasks/celery_app.py` — existing `include` list, no beat schedule yet
- `backend/app/tasks/sentiment_tasks.py` — pattern for async Celery tasks
- `backend/app/database.py` — `async_session_factory` (or equivalent)

---

## ST-C — Indicator Overlay System (ChartCanvas)  [ ] pending

### Intent
`chartStore.ts` has full CRUD for `IndicatorConfig[]` and `lib/indicators/index.ts`
computes all values, but `ChartCanvas.tsx` never reads `indicators` from the store or
renders any overlay series. This ST wires them together: overlays (SMA, EMA, BB, RSI,
MACD) render as lightweight-charts v5 `LineSeries` on the price pane, with RSI and MACD
rendered on separate sub-panes.

### Expected Outcomes
- `ChartPanel/index.tsx` passes `indicators` from `chartStore` down to `ChartCanvas`.
- `ChartCanvas.tsx` maintains an `overlaySeriesRef` map, keyed by `indicator.id`. When
  `indicators` changes, it diffs the map: removes deleted series, adds new ones, hides
  toggled-off series, shows toggled-on series.
- Supported overlays on price pane: `sma`, `ema`, `wma`, `bb` (3 lines: upper/mid/lower).
- Supported sub-pane overlays: `rsi` (separate pane with 70/30 reference lines), `macd`
  (histogram + signal + MACD lines).
- `ChartToolbar.tsx` gains an "Indicators" dropdown button that lets the user pick a type
  and add it; tapping an active indicator's pill removes it. Uses `addIndicator` /
  `removeIndicator` / `toggleIndicator` actions from `chartStore`.
- vitest: the new indicator-overlay logic is pure (compute → array → setData); unit tests
  cover the compute path. Chart rendering itself stays mocked (same pattern as
  `MultiTimeframePanel`).
- `eslint --max-warnings=0`, `tsc --noEmit`, `vitest`, `next build` all pass.

### Todo List
1. Update `ChartPanel/index.tsx`:
   - Import `addIndicator`, `removeIndicator`, `toggleIndicator` from `useChartStore`.
   - Pass `indicators={config.indicators}`, `onAddIndicator`, `onRemoveIndicator`,
     `onToggleIndicator` as props to `ChartCanvas` and `ChartToolbar`.
2. Update `ChartCanvas.tsx`:
   - Add `indicators: IndicatorConfig[]` prop.
   - Import all indicator functions from `@/lib/indicators`.
   - Add a `overlaySeriesRef` map (`useRef<Map<string, ISeriesApi<"Line">>>`).
   - Add a new `useEffect([indicators, bars])` that:
     a. Removes series for any `id` that no longer appears in `indicators`.
     b. For each `indicator` in `indicators`:
        - If not yet created: compute values from `bars`, call `chart.addSeries(LineSeries, opts)`,
          `series.setData(lineData)`, store in map.
        - If `visible` changed: `series.applyOptions({ visible: indicator.visible })`.
     c. For `bb`: create 3 line series (upper, mid, lower) stored under
        `id+"_upper"`, `id+"_mid"`, `id+"_lower"`.
   - RSI and MACD: add to a second price scale (`rightPriceScale: { scaleMargins... }`).
     Keep the implementation simple — render them on the same pane with a separate right
     scale rather than a fully independent pane (lightweight-charts v5 pane API is in beta).
3. Update `ChartToolbar.tsx`:
   - Add `indicators`, `onAddIndicator`, `onRemoveIndicator`, `onToggleIndicator` props.
   - Add an "Ind ▾" dropdown button that shows a list: SMA, EMA, WMA, BB, RSI, MACD.
   - Clicking a type calls `onAddIndicator` with a default `IndicatorConfig`
     `{id: uuid(), type, params: defaultParams(type), visible: true}`.
   - Render active indicator pills in the toolbar (click pill to remove).
4. Add vitest tests in `frontend/tests/unit/indicators.test.ts` (already exists) for any
   new compute paths. Add a smoke render test for `ChartPanel` in `panels_new.test.tsx`
   (mock `ChartCanvas` the same way `MultiTimeframePanel` is mocked, since it uses canvas).
5. Run `eslint --max-warnings=0`, `tsc --noEmit`, `vitest`, `next build`.

### Relevant Context
- `frontend/components/panels/ChartPanel/ChartCanvas.tsx` — lines 11-23 (imports), 82-193
  (series effect). `LineSeries` is already imported.
- `frontend/components/panels/ChartPanel/ChartToolbar.tsx` — lines 30-36 (props interface).
- `frontend/store/chartStore.ts` — `IndicatorConfig`, `addIndicator`, `removeIndicator`,
  `toggleIndicator`
- `frontend/lib/indicators/index.ts` — `sma`, `ema`, `wma`, `bollingerBands`, `rsi`, `macd`
- `frontend/tests/unit/panels_new.test.tsx` lines 31-45 — mock pattern for canvas panels

---

## ST-D — BacktestPanel Frontend  [ ] pending

### Intent
`POST /api/v1/backtest/run` exists and the backtesting engine is complete, but there is
no UI to trigger it. `BacktestPanel` provides: a form to configure a backtest, an equity
curve chart, a metrics table, a trade log, and a link to the HTML report.

### Expected Outcomes
- `frontend/components/panels/BacktestPanel/index.tsx` renders:
  - Form: symbol text input, start/end date pickers, strategy selector (sma_cross; more
    added as ST-E strategies are built), fast/slow params, engine radio (vectorized / event).
  - Submit button calls `POST /api/v1/backtest/run`.
  - Loading skeleton while running.
  - Results view: equity curve as a lightweight-charts `LineSeries`, metrics table
    (total return, Sharpe, max drawdown, win rate, profit factor, trade count), trade log
    tab, HTML report download link.
- Panel is registered in `dashboard/page.tsx` and `layoutStore.ts`.
- vitest smoke test (mock fetch + mock ChartCanvas).
- `eslint`, `tsc --noEmit`, `vitest`, `next build` pass.

### Todo List
1. Create `frontend/components/panels/BacktestPanel/index.tsx`:
   - Local state: `form` (symbol, startDate, endDate, strategy, fast, slow, engine),
     `status` (idle | running | done | error), `result` (BacktestResult | null).
   - `handleRun`: POST to `/api/v1/backtest/run` via `apiRequest`; set status.
   - Results view:
     - Equity curve: `useEffect` → `chart.addSeries(LineSeries, ...)` → `series.setData()`
       where data is `result.equity_curve.map((v, i) => ({time: i, value: v}))`.
       Wrap in `useRef` + cleanup (same pattern as `ChartCanvas.tsx`).
     - Metrics grid: 2-column CSS grid, keys from `result.metrics`.
     - Trade log: scrollable table with `symbol, side, qty, entry_price, exit_price, pnl`.
     - HTML report link: `<a href={result.report_url}>Download Report</a>` (if present).
2. Add to `frontend/app/(dashboard)/dashboard/page.tsx`:
   - Import `BacktestPanel`.
   - Add `<div id="backtest"><BacktestPanel /></div>` in the panel grid section.
3. Add to `frontend/store/layoutStore.ts`:
   - Add `{ i: "backtest", x: 4, y: 86, w: 8, h: 20, minW: 4, minH: 12 }` to
     `DEFAULT_LAYOUT`.
4. Add vitest test in `frontend/tests/unit/panels_new.test.tsx`:
   - Mock `apiRequest` to return a minimal `BacktestResult`.
   - Assert form renders with correct field labels.
   - Assert metrics table renders after mock result.
5. Run `eslint --max-warnings=0`, `tsc --noEmit`, `vitest`, `next build`.

### Relevant Context
- `backend/app/api/v1/backtest.py` — request/response schema for `POST /backtest/run`
- `backtesting/engine/base.py` — `BacktestResult`, `Trade` dataclass shapes
- `frontend/components/panels/ChartPanel/ChartCanvas.tsx` — canvas/chart lifecycle pattern
- `frontend/lib/api/client.ts` — `apiRequest` usage pattern
- `frontend/store/layoutStore.ts` — `DEFAULT_LAYOUT` (lines 35-55)

---

## ST-E — Additional Backtesting Strategies  [ ] pending

### Intent
Only `SmaCrossStrategy` is available. `RSIMeanReversionStrategy`, `MACDCrossStrategy`,
`BollingerBandStrategy`, and `VWAPReversionStrategy` are needed for practical use and
to exercise the backtest API more thoroughly. The `BacktestPanel` strategy selector
(ST-D) should list all four.

### Expected Outcomes
- Four new strategy files under `backtesting/strategies/`:
  - `rsi_mean_reversion.py` — buy when RSI < 30, sell when RSI > 70.
  - `macd_cross.py` — long when MACD line crosses above signal; exit on cross below.
  - `bollinger_band.py` — buy at lower band touch (close < lower), sell at upper touch.
  - `vwap_reversion.py` — intraday: buy when close < VWAP by threshold, sell when > VWAP.
- `backtesting/strategies/__init__.py` updated to export all four.
- `backend/app/api/v1/backtest.py` `_get_strategy()` updated to handle the four new
  type strings: `"rsi_mean_reversion"`, `"macd_cross"`, `"bollinger_band"`,
  `"vwap_reversion"`.
- Tests added to `backtesting/tests/test_engines.py` for each new strategy: at least one
  test that runs the strategy through the vectorized engine and asserts metrics keys are
  present.
- All existing 33 backtesting tests still pass; new tests push count higher.
- `ruff check`, `bandit -ll`, `pytest` pass.

### Todo List
1. Create `backtesting/strategies/rsi_mean_reversion.py`:
   - `RSIMeanReversionStrategy(period=14, oversold=30, overbought=70, allow_short=False)`
   - Compute RSI from `data["close"]`; signal: +1 when RSI < oversold, -1 (if allow_short)
     or 0 when RSI > overbought, 0 otherwise.
2. Create `backtesting/strategies/macd_cross.py`:
   - `MACDCrossStrategy(fast=12, slow=26, signal=9, allow_short=False)`
   - Compute MACD line and signal; +1 on positive cross, 0 (or -1) on negative.
3. Create `backtesting/strategies/bollinger_band.py`:
   - `BollingerBandStrategy(period=20, std_dev=2.0, allow_short=False)`
   - Signal +1 when close < lower band; 0 when close > upper band; hold otherwise.
4. Create `backtesting/strategies/vwap_reversion.py`:
   - `VWAPReversionStrategy(threshold_pct=0.5, allow_short=False)`
   - Compute rolling VWAP from `data["close"]`, `data["high"]`, `data["low"]`,
     `data["volume"]`; signal +1 when close < VWAP * (1 - threshold/100).
5. Update `backtesting/strategies/__init__.py` to export all four.
6. Update `backend/app/api/v1/backtest.py` `_get_strategy()` with four new `elif` branches.
7. Add tests in `backtesting/tests/test_engines.py`:
   - For each strategy: instantiate, run through `VectorizedEngine`, assert
     `result.metrics` has `"total_return"` and `"sharpe_ratio"` keys.
8. Run `ruff check`, `bandit -ll`, `pytest`.

### Relevant Context
- `backtesting/strategies/sma_cross.py` — reference implementation pattern
- `backtesting/engine/base.py` — `Strategy` protocol (`generate_signals` signature)
- `backtesting/engine/vectorized.py` — `VectorizedEngine.run(data, strategy)`
- `backend/app/api/v1/backtest.py` — `_get_strategy()` dispatch function

---

## ST-F — Ticker Sparklines in WatchlistPanel  [ ] pending

### Intent
`WatchlistPanel` rows show price/change/volume but no visual trend line.
A 20-bar close-price sparkline in each row matches Bloomberg/ThinkorSwim aesthetics
and conveys trend at a glance without requiring an extra API call — the data is already
in `marketDataStore` (live quotes) or can be fetched lazily per symbol.

### Expected Outcomes
- Each `WatchlistRow` renders a small SVG sparkline (≈60×24 px) showing the last 20
  close prices as a polyline, colored green/red based on net direction.
- Sparkline data source: last 20 prices from a per-symbol price history buffer maintained
  in `marketDataStore` (append each incoming quote price, keep last 20). No extra API call
  on each render.
- `marketDataStore` gains a `priceHistory: Record<string, number[]>` slice that appends
  on each quote update (capped at 20 entries).
- WatchlistPanel table: add a "Spark" column header; `WatchlistRow` receives `sparkline:
  number[]` prop and renders the SVG inline.
- vitest: add test that `WatchlistRow` renders an `<svg>` when sparkline data is provided;
  renders `"—"` when data is empty.
- `eslint`, `tsc --noEmit`, `vitest`, `next build` pass.

### Todo List
1. Update `frontend/store/marketDataStore.ts`:
   - Add `priceHistory: Record<string, number[]>` to state.
   - In the quote-update reducer, append `quote.price` to `priceHistory[symbol]` and
     slice to last 20 entries.
2. Create `frontend/components/ui/Sparkline.tsx`:
   - Props: `data: number[], width?: number, height?: number`.
   - Compute min/max, scale to SVG coords, render `<polyline points="...">`.
   - Color: `#00d084` if `data[last] >= data[0]`; `#ef4444` otherwise.
   - Returns `null` when `data.length < 2`.
3. Update `frontend/components/panels/WatchlistPanel/index.tsx`:
   - Subscribe to `priceHistory` from `marketDataStore`.
   - Add `sparkline` column header to table.
   - Pass `sparkline={priceHistory[symbol] ?? []}` to `WatchlistRow`.
4. Update `WatchlistRow` props and render `<Sparkline data={sparkline} />` in new cell.
5. Add vitest tests.
6. Run `eslint --max-warnings=0`, `tsc --noEmit`, `vitest`, `next build`.

### Relevant Context
- `frontend/store/marketDataStore.ts` — existing `quotes` slice pattern
- `frontend/components/panels/WatchlistPanel/index.tsx` — `WatchlistRow` at line 186
- `frontend/hooks/useMarketData.ts` — WebSocket message dispatch to marketDataStore

---

## ST-G — WebSocket Resilience (Exponential Backoff + Jitter)  [ ] pending

### Intent
`useWebSocket.ts` reconnects with a fixed delay and no jitter, which causes reconnect
storms when many clients come back from a network blip at the same time. This ST upgrades
it to exponential backoff with ±25% jitter and a circuit-breaker cap.

### Expected Outcomes
- `useWebSocket.ts` replaces `reconnectDelay` param with `baseDelay` (default 100 ms).
- Reconnect delay for attempt `n`: `min(baseDelay * 2^n, 1600) * (0.75 + 0.5 * Math.random())`.
- After `maxReconnectAttempts` (default 10), the hook stops trying and calls a new
  `onMaxRetriesExceeded` optional callback.
- Existing callers (`useMarketData.ts`, `useAuth.ts` if any) pass `baseDelay` — not
  breaking because the old `reconnectDelay` prop is renamed but default semantics are
  compatible (callers that don't pass it get backoff behaviour automatically).
- vitest: add `frontend/tests/unit/useWebSocket.test.ts` — use `vi.useFakeTimers()` to
  assert delays grow exponentially and stay within the 1600 ms cap with jitter bounds.
- `eslint`, `tsc --noEmit`, `vitest`, `next build` pass.

### Todo List
1. Update `frontend/hooks/useWebSocket.ts`:
   - Rename `reconnectDelay` → `baseDelay` (default 100).
   - Compute delay in `onclose`: `clamp(baseDelay * 2 ** reconnectCount, 100, 1600) * jitter`.
   - Add `onMaxRetriesExceeded?: () => void` to options interface.
   - Call `onMaxRetriesExceeded` when `reconnectCount >= maxReconnectAttempts`.
2. Update any callers that pass `reconnectDelay` prop explicitly.
3. Create `frontend/tests/unit/useWebSocket.test.ts` with fake-timer tests.
4. Run `eslint --max-warnings=0`, `tsc --noEmit`, `vitest`, `next build`.

### Relevant Context
- `frontend/hooks/useWebSocket.ts` — full file (95 lines)
- `frontend/hooks/useMarketData.ts` — passes `reconnectDelay`

---

## ST-H — Volatility Surface Panel  [ ] pending

### Intent
Planned in Phase 5 of the original spec. Renders a 3D implied-volatility surface
(strikes × expirations) for the active symbol using Three.js or D3 + WebGL.
The backend already has `app/services/options/greeks.py` with `implied_volatility()`.
A new endpoint aggregates IV across the options chain and returns the surface matrix.

### Expected Outcomes
- `GET /api/v1/options/iv-surface?symbol=AAPL` returns a grid of
  `{ strike, expiry_days, iv }` objects computed from the demo options chain.
- `frontend/components/panels/VolatilityPanel/index.tsx` fetches the surface and
  renders a 3D mesh using Three.js (`@react-three/fiber` + `@react-three/drei`).
  Falls back to a 2D D3 heatmap when WebGL is unavailable.
- Panel registered in dashboard/page + layoutStore.
- vitest: mocks Three.js; tests that the panel renders a loading state, then a canvas
  element on successful fetch.
- `eslint`, `tsc --noEmit`, `vitest`, `next build` pass.
- `ruff check`, `bandit -ll`, `pytest` pass.

### Todo List
1. Add `GET /options/iv-surface` to `backend/app/api/v1/options.py`.
   - Accept `symbol: str` query param.
   - Return a list of `{strike, expiry_days, iv}` dicts derived from the demo options
     chain data already present in `OptionsChainPanel` backend logic.
2. Install frontend deps: `@react-three/fiber`, `@react-three/drei`, `three` (and
   corresponding `@types/three`). Confirm these are latest stable versions.
3. Create `frontend/components/panels/VolatilityPanel/index.tsx`:
   - Fetch IV surface from endpoint on mount.
   - Render a `<Canvas>` (react-three-fiber) with a `<mesh>` geometry built from the
     surface grid.
   - Colour by IV magnitude (low = blue, high = red).
   - If WebGL unavailable (detect via `canvas.getContext("webgl")`), render a D3 heatmap
     fallback as a simple SVG grid.
4. Register in `dashboard/page.tsx` and `layoutStore.ts`.
5. Add vitest mock + smoke test.
6. Run all validations.

### Relevant Context
- `backend/app/services/options/greeks.py` — `implied_volatility()` function
- `backend/app/api/v1/options.py` — existing options routes
- `frontend/components/panels/OptionsChainPanel/index.tsx` — data shape reference

---

## ST-I — Volume Profile (VPVR)  [ ] pending

### Intent
Volume Profile Visible Range is a high-value indicator for institutional-grade charting.
It requires per-bar data, so it can't be computed purely client-side without all bars.
A backend endpoint computes VPVR for a symbol/range; the frontend renders it as a
horizontal bar histogram overlaid on the right side of the chart.

### Expected Outcomes
- `GET /api/v1/market/vpvr?symbol=AAPL&start=...&end=...&bins=24` returns `{price_levels:
  [{price, volume, is_poc}]}` (POC = point of control, highest volume price).
- `ChartCanvas.tsx` can optionally render VPVR as horizontal bars using a Canvas overlay
  (custom primitive painter, not a lightweight-charts series).
- An "Add VPVR" button in `ChartToolbar` triggers the fetch and enables rendering.
- `ruff`, `bandit`, `pytest`, `eslint`, `tsc`, `vitest`, `next build` pass.

### Todo List
1. Add `GET /market/vpvr` to `backend/app/api/v1/market.py`:
   - Fetch bars for symbol/range, aggregate volume per price bin, identify POC.
2. Add corresponding unit test in `backend/tests/`.
3. Add VPVR overlay rendering in `ChartCanvas.tsx` using a `useEffect` that draws onto
   a transparent `<canvas>` overlay absolutely positioned over the chart container.
4. Wire toolbar button → fetch → render toggle.
5. Run all validations.

### Relevant Context
- `backend/app/api/v1/market.py` — existing market endpoints
- `frontend/components/panels/ChartPanel/ChartCanvas.tsx` — container div ref for overlay
- `frontend/lib/indicators/index.ts` — volume indicator patterns (OBV, VWAP)

---

## ST-J — Advanced Order Features  [ ] pending

### Intent
`OrderEntryPanel` supports basic market/limit/stop orders. Bracket orders (automatic
stop-loss + take-profit attached to entry), OCO pairs, and order modification are
required for practical trading workflows.

### Expected Outcomes
- `OrderEntryPanel` gains a "Bracket" toggle: when enabled, two new fields appear
  (stop-loss price, take-profit price). On submit, three orders are sent: the entry
  + a stop + a limit at the take-profit price, linked as a bracket in Alpaca.
- OCO: a checkbox "Cancel other on fill". Sends an Alpaca OCO order pair.
- Order modification: in the MY ORDERS tab, open orders get an "Edit" action that opens
  an inline form to change `limit_price` or `qty`. Backend endpoint `PATCH /orders/{id}`.
- Fill notifications: when the `/ws/orders` receives a `filled` status update,
  `PortfolioPanel` automatically refreshes its positions via a Zustand event.
- `pytest`, `vitest`, `next build` pass.

### Todo List
1. Backend: add `PATCH /api/v1/orders/{order_id}` to `backend/app/api/v1/orders.py`
   that calls `PUT /v2/orders/{id}` on Alpaca (simulates modification in demo mode).
2. Backend: update `place_order` in service to support `order_class: "bracket"` with
   `take_profit` and `stop_loss` params forwarded to Alpaca.
3. Backend: add unit tests for bracket + modification paths.
4. Frontend: update `OrderEntryPanel` with bracket UI controls and OCO checkbox.
5. Frontend: `PATCH` call for order modification in MY ORDERS tab.
6. Frontend: subscribe `PortfolioPanel` to an `orderFill` Zustand event (via a
   `useEffect` on the orders store `lastFill` field) that triggers position refresh.
7. Run all validations.

### Relevant Context
- `backend/app/api/v1/orders.py` — existing POST/GET/DELETE
- `backend/app/services/orders/service.py` — `place_order`, `cancel_order`
- `frontend/components/panels/OrderEntryPanel/index.tsx`
- `frontend/components/panels/PortfolioPanel/index.tsx`

---

## ST-K — Bayesian Optimization (Optuna)  [ ] pending

### Intent
`WalkForwardOptimizer` uses exhaustive grid search, which is O(n^m). For strategies
with 3+ parameters this is impractical. Optuna Bayesian optimization (TPE sampler)
reduces trials by 10–100× for the same result quality.

### Expected Outcomes
- `backtesting/optimization/bayesian.py` with `BayesianOptimizer(strategy_class, param_space,
  n_trials, metric)`.
- `POST /api/v1/backtest/optimize` endpoint that accepts a strategy name, param space
  dict, and n_trials; runs Optuna; returns best params + all trial results.
- Optuna added to `backend/pyproject.toml` dependencies.
- Tests in `backtesting/tests/` covering at least 3-trial optimization run.
- `ruff`, `bandit`, `pytest` pass.

### Todo List
1. Add `optuna` to `backend/pyproject.toml` (latest stable version).
2. Create `backtesting/optimization/bayesian.py`:
   - `BayesianOptimizer(strategy_class, param_space, engine, metric, n_trials, data)`.
   - `param_space` is a dict mapping param name to `(low, high, step)` tuples.
   - Objective function: instantiate strategy with trial params → run engine → return metric.
   - Use `optuna.create_study(direction="maximize", sampler=TPESampler())`.
   - Return `{best_params, best_value, all_trials}`.
3. Add `POST /backtest/optimize` to `backend/app/api/v1/backtest.py`.
4. Add tests.
5. Run `ruff check`, `bandit -ll`, `pytest`.

### Relevant Context
- `backtesting/optimization/walk_forward.py` — existing optimizer pattern
- `backtesting/engine/vectorized.py` — `VectorizedEngine.run()`
- `backend/app/api/v1/backtest.py` — existing lazy-import pattern

---

## ST-L — Strategy Builder UI  [ ] pending

### Intent
A drag-and-drop node canvas (react-flow) where non-programmers compose entry/exit logic
from building blocks (indicator nodes, comparator nodes, AND/OR logic nodes, action nodes).
The canvas serializes to a JSON config which is sent to the backtest API via a new
`DynamicStrategy` Python class.

### Expected Outcomes
- `frontend/components/panels/StrategyBuilderPanel/index.tsx` — react-flow canvas with:
  - Node palette: indicator nodes (RSI, SMA, MACD), comparator nodes (>, <, crosses),
    logic nodes (AND, OR), entry/exit action nodes.
  - Save button serializes to JSON; Run button sends to `POST /api/v1/backtest/run`.
- `backend/app/api/v1/strategies.py` — CRUD for saved strategy configs
  (`POST /strategies`, `GET /strategies`, `DELETE /strategies/{id}`).
- `backtesting/strategies/dynamic.py` — `DynamicStrategy(config: dict)` that interprets
  the JSON node graph into `generate_signals()` logic.
- Panel registered in dashboard.
- Tests: unit test for `DynamicStrategy` with a simple "RSI < 30 → buy" config.

### Todo List
1. Install `reactflow` (latest stable) as a frontend dependency.
2. Create `StrategyBuilderPanel` with node types, palette sidebar, canvas.
3. Create `DynamicStrategy` Python class.
4. Create `backend/app/api/v1/strategies.py` CRUD endpoints.
5. Register panel in dashboard + layoutStore.
6. Add tests.
7. Run all validations.

### Relevant Context
- `backtesting/strategies/sma_cross.py` — strategy protocol to match
- `backend/app/api/v1/backtest.py` — `_get_strategy()` to extend
- `frontend/components/panels/BacktestPanel/index.tsx` (ST-D) — consumer of the JSON

---

## ST-M — AI Trade Journal  [ ] pending

### Intent
On every filled order, a Celery task fetches news sentiment at entry/exit, technical
indicator state (RSI, MACD), and sends a structured GPT-4o prompt. The response is
stored in MongoDB and surfaced in `TradeJournalPanel`.

### Expected Outcomes
- `backend/app/tasks/journal_tasks.py` — `analyze_trade(order_id)` Celery task.
- `TradeJournal` MongoDB collection (defined in `backend/app/models/mongodb/`).
- `GET /api/v1/journal` returns journal entries for the current user.
- `frontend/components/panels/TradeJournalPanel/index.tsx` — lists journal entries with
  AI analysis text, sentiment score, technical context, and trade outcome.
- Registered in dashboard + layoutStore.
- Tests: mock OpenAI client; assert journal entry is saved with expected keys.

### Todo List
1. Create `backend/app/tasks/journal_tasks.py`.
2. Wire `analyze_trade.delay(order_id)` call in the order fill path (in ST-B's
   order polling task or in the order fill handler).
3. Create `GET /api/v1/journal` endpoint.
4. Create `TradeJournalPanel` frontend component.
5. Register panel.
6. Add tests.
7. Run all validations.

### Relevant Context
- `backend/app/tasks/sentiment_tasks.py` — OpenAI/FinBERT task pattern
- `backend/app/tasks/order_tasks.py` (ST-B) — fill detection hook
- `backend/app/services/audit/logger.py` — async DB write pattern

---

## ST-N — Load Tests (k6)  [ ] pending

### Intent
`tests/load/` is empty. A k6 script targeting WebSocket fan-out (`/ws/market`) is needed
to validate the 1,000 concurrent subscribers design goal.

### Expected Outcomes
- `tests/load/ws_market.js` — k6 script that opens 1,000 virtual user WebSocket
  connections to `/ws/market`, subscribes to 5 symbols each, and asserts p99 message
  latency < 100 ms.
- `tests/load/rest_auth.js` — k6 script for REST auth flow (login → get token → hit
  5 endpoints) at 200 RPS; assert p99 < 500 ms and error rate < 0.1%.
- `Makefile` gains `make load-test` target.
- No k6 results in CI (k6 not installed by default) — tests are run manually.

### Todo List
1. Create `tests/load/ws_market.js` using k6 WebSocket API.
2. Create `tests/load/rest_auth.js` using k6 HTTP API.
3. Add `load-test` Makefile target.
4. Document how to install k6 and run tests in `docs/developer/load-testing.md`.

### Relevant Context
- `tests/load/` — empty directory
- `Makefile` — existing targets pattern
- `backend/app/api/ws/router.py` — `/ws/market` WebSocket endpoint

---

## ST-O — Architecture Decision Records  [ ] pending

### Intent
`docs/developer/` and `docs/decisions/` are empty. Four ADRs are needed to document
key architectural choices for future contributors.

### Expected Outcomes
Four ADR files created in `docs/decisions/`:
- `ADR-001-frontend-framework.md` — Next.js 16 App Router choice
- `ADR-002-database-selection.md` — TimescaleDB + PostgreSQL + Redis + MongoDB
- `ADR-003-websocket-architecture.md` — Single connection + Zustand fan-out
- `ADR-004-backtesting-engine-design.md` — Vectorized + event-driven dual engine

Each ADR follows the MADR format: Status, Context, Decision, Consequences.

### Todo List
1. Create `docs/decisions/ADR-001-frontend-framework.md`.
2. Create `docs/decisions/ADR-002-database-selection.md`.
3. Create `docs/decisions/ADR-003-websocket-architecture.md`.
4. Create `docs/decisions/ADR-004-backtesting-engine-design.md`.
5. Create `docs/developer/load-testing.md` (referenced in ST-N).

---

## ST-P — Kubernetes Manifests + Terraform IaC  [ ] pending

### Intent
`infra/k8s/` is empty. Docker Compose is sufficient for local dev but cloud deployment
requires Kubernetes manifests (or Terraform ECS Fargate, whichever is lower-friction
for the project's scale). This ST produces a working `infra/k8s/` directory and a
Terraform module for AWS ECS Fargate.

### Expected Outcomes
- `infra/k8s/` contains Deployment + Service manifests for: frontend, backend, celery-worker,
  redis, postgres (or references to managed services).
- `infra/terraform/` contains an ECS Fargate module with all resources from §14.9:
  ECS services, RDS, ElastiCache, DocumentDB, ALB, ACM, Route53, Secrets Manager.
- All secrets referenced via AWS Secrets Manager ARNs — no values in code.
- `Makefile` gains `make tf-plan` and `make tf-apply` targets.

### Todo List
1. Create Kubernetes manifests in `infra/k8s/`.
2. Create Terraform module in `infra/terraform/`.
3. Add Makefile targets.
4. Document deployment steps in `docs/developer/deployment.md`.

---

## ST-Q — Regime Detection (HMM)  [ ] pending

### Intent
`ml/models/hmm/` is scaffolded but empty. A Gaussian HMM trained on VIX + yield-curve +
momentum features classifies the current market regime. The regime state is surfaced in
`MacroPanel` (header tint) and gates position sizing in `RiskPanel`.

### Expected Outcomes
- `ml/models/hmm/model.py` — `RegimeDetector` class wrapping `hmmlearn.GaussianHMM`.
- `ml/models/hmm/train.py` — training script using FRED VIX + yield spread data.
- `GET /api/v1/macro/regime` backend endpoint returns `{regime: "trending" | "mean_reverting"
  | "high_volatility" | "low_volatility", confidence: float}`.
- `MacroPanel` header background tints based on regime color.
- Tests for `RegimeDetector.predict()` with synthetic feature data.

---

## ST-R — Real-Time Indicator Streaming (SSE)  [ ] pending

### Intent
Client-side indicator compute is consistent within the browser but diverges from the
Python backtesting engine when period lengths differ. A server-side SSE endpoint
computing indicator values (TA-Lib) for a symbol, cached in Redis per bar, eliminates
the divergence and enables screener filters on live indicator values.

### Expected Outcomes
- `GET /api/v1/market/indicators/{symbol}` returns a JSON snapshot of current indicator
  values: `{sma_20, ema_50, rsi_14, macd_signal, bb_upper, bb_lower}`.
- Redis cache: refreshed on each new bar close, 5-minute TTL for intraday.
- `ScreenerPanel` gains indicator filter conditions (RSI < 30, EMA crossover, etc.).
- Tests for the endpoint.

---

## ST-S — Portfolio Import (CSV + Broker OAuth)  [ ] pending

### Intent
Users with existing positions cannot use `PortfolioPanel` meaningfully without importing
their holdings. A CSV upload + optional broker OAuth flow normalizes positions into the
`positions` table and recalculates P&L live.

### Expected Outcomes
- `POST /api/v1/portfolio/import` accepts a CSV multipart upload with columns
  `symbol, quantity, avg_price, date_opened`.
- Parses, validates, upserts into `positions` table.
- Frontend: `PortfolioPanel` gains an "Import" button that opens a file-picker.
- Optional: TD Ameritrade / Interactive Brokers OAuth flow (deferred to a sub-task if
  scope is too large).

---

## ST-T — Multi-User & Workspace Mode  [ ] pending

### Intent
The current auth system is single-user by default. A workspace model (GitHub
organization-style) allows traders to share watchlists, screener presets, and alert
configs.

### Expected Outcomes
- Alembic migration adds `workspaces`, `workspace_members` tables.
- RBAC gains `workspace_admin` role.
- Watchlist, Screener, Alert models gain `workspace_id` FK (nullable — personal items
  have no workspace).
- `GET /api/v1/workspaces` + `POST` + `DELETE` endpoints.
- Frontend: workspace switcher in the top navigation bar.

---

## ST-U — Tick Data Recorder + Replay  [ ] pending

### Intent
A Celery task records raw ticks from the Alpaca WebSocket into the `ticks` TimescaleDB
hypertable. A "tape replay" mode in the backtesting engine replays historical ticks at
configurable speed for microstructure-aware strategy testing.

### Expected Outcomes
- `backend/app/tasks/data_tasks.py` `record_ticks()` task upgraded from stub to real
  implementation.
- `backtesting/engine/tick_replay.py` — `TickReplayEngine(speed_multiplier)` that
  processes `ticks` rows as market events.
- Tests for tick recorder (mock Alpaca WS) and replay engine.

---

## Execution Order Recommendation

Work through sub-tasks in this sequence to maximise momentum and keep validation green:

```
ST-A → ST-B → ST-C → ST-D → ST-E → ST-F → ST-G
 (backend data)   (frontend features)    (UX polish)

ST-H → ST-I → ST-J                    (advanced chart + orders)
ST-K → ST-L → ST-M                    (quant + AI features)
ST-N → ST-O → ST-P                    (ops / infrastructure)
ST-Q → ST-R → ST-S → ST-T → ST-U     (ML + platform expansion)
```

Each sub-task is independently mergeable; implement one at a time, run full validation
before starting the next.
