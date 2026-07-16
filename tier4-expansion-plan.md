# QuantNexus Tier 4 Expansion Plan

**Goal:** Implement all eight previously-deferred Tier 4 items AND wire in a full cohort of new
data providers (Financial Modeling Prep, EarningsCall.ai, StockTwits, OpenInsider, Morningstar,
FactSet, Capital IQ, PitchBook, Reuters, Benzinga, Bloomberg Terminal, AlphaSpace, eMoney,
SEC EDGAR extensions) in priority order.

**Scope boundary:** Polygon.io and SEC EDGAR are already implemented; this plan extends them
where new endpoints are available. OANDA adapter stub exists in `.env.example` but the adapter
itself is not yet written.

**Approach:** Work in six tracks. All tracks run independently — there is no mandatory
ordering between tracks except within-track dependencies noted per sub-task. Infrastructure
tracks (E, F) run in parallel with data tracks (A, B, C, D).

**Free-tier first:** All data provider adapters are scoped to free-tier credentials only.
Paid-tier upgrade paths are documented per adapter but no paid credentials are assumed.

**Track F sequencing:** Track F (C++ engine) begins only after Track E (MLOps pipeline) is
complete.

---

## Track A — Data Provider Expansion (Free / Low-Cost APIs First)

### A-1 · Financial Modeling Prep (FMP) Adapter

- **Status:** `[x] done`
- **Intent:** Wire FMP as a primary source for fundamentals (income statement, balance sheet, cash
  flow, key metrics, DCF valuation, analyst estimates, earnings history, insider transactions,
  institutional holders). FMP free tier gives 250 requests/day with a generous set of endpoints
  that cover everything needed here. This fills a data gap — the existing `Fundamental` ORM model
  has placeholder fields that nothing populates today.
- **API:** `https://financialmodelingprep.com/api/v3` — REST, JSON, API-key auth via `?apikey=`.
- **Access tier needed:** Free tier (250 req/day). Implementation is scoped to free-tier
  endpoints only. When upgrading to Starter ($29/mo), no code changes are needed — only a new
  API key with a higher quota.
- **Expected Outcomes:**
  - `FMPAdapter` class in `backend/app/services/fundamentals/fmp.py`
  - Endpoints: income statement, balance sheet, cash flow (annual + quarterly), key metrics, DCF
    intrinsic value, earnings history, analyst EPS/revenue estimates, insider transactions,
    institutional holders, company profile
  - Celery task `refresh_fundamentals(symbol)` that writes into `Fundamental` ORM model (and new
    `InsiderTransaction`, `InstitutionalHolder` models if FMP data warrants it)
  - New API route `GET /api/v1/fundamentals/{symbol}` → returns merged FMP payload
  - `FundamentalsPanel` frontend component OR extension of `ScreenerPanel` to display FMP data
  - Unit tests with httpx mock
- **Todo:**
  1. Read `backend/app/services/macro/fred.py` to understand the Redis-caching + retry pattern to
     replicate.
  2. Read `backend/app/models/fundamental.py` for current ORM schema.
  3. Implement `FMPAdapter` with methods: `get_profile()`, `get_income_statement()`,
     `get_balance_sheet()`, `get_cash_flow()`, `get_key_metrics()`, `get_dcf()`,
     `get_earnings_history()`, `get_analyst_estimates()`, `get_insider_transactions()`,
     `get_institutional_holders()`.
  4. Add `FMP_API_KEY` to `backend/app/core/config.py` and `.env.example`.
  5. Extend `Fundamental` ORM model with new columns (DCF value, sector, industry, description,
     beta, dividend yield). Add Alembic migration.
  6. Add `InsiderTransaction` and `InstitutionalHolder` ORM models. Add migration.
  7. Write Celery task `refresh_fundamentals` in `backend/app/tasks/data_tasks.py`.
  8. Add `GET /api/v1/fundamentals/{symbol}` route to
     `backend/app/api/v1/fundamentals.py` and register in `backend/app/api/v1/router.py`.
  9. Create `FundamentalsPanel` in `frontend/components/panels/FundamentalsPanel/index.tsx` —
     tabs for Profile / Income / Balance Sheet / Cash Flow / Insiders / Institutions.
  10. Add panel to `dashboard/page.tsx` and `DEFAULT_LAYOUT` in `layoutStore.ts`.
  11. Write unit tests (`backend/tests/unit/test_fmp_adapter.py`).
- **Relevant Context:**
  - Pattern to follow: `backend/app/services/macro/fred.py` (Redis cache, retry)
  - ORM pattern: `backend/app/models/fundamental.py`
  - Celery task pattern: `backend/app/tasks/data_tasks.py` (`refresh_ohlcv`)
  - Route pattern: `backend/app/api/v1/macro.py`

---

### A-2 · OpenInsider Adapter

- **Status:** `[x] done`
- **Intent:** Scrape OpenInsider's public RSS/CSV export (no API key required; no ToS violation —
  it is a public aggregator of SEC Form 4 filings) to surface insider buy/sell signals.
  Complements the FMP insider transactions endpoint with real-time filings.
- **API:** `http://openinsider.com/screener?s={symbol}&fd=-1&td=-1&...` returns CSV rows.
  Alternative: `http://openinsider.com/rss?s={symbol}` returns RSS XML.
- **Access tier needed:** Free (public data).
- **Expected Outcomes:**
  - `OpenInsiderAdapter` in `backend/app/services/news/openinsider.py`
  - Parses Form 4 rows: filing_date, insider_name, title, transaction_type (P/S), shares,
    price_per_share, total_value, shares_owned_after
  - New API route `GET /api/v1/fundamentals/{symbol}/insider-flow` returns last 90 days of trades
  - Insider flow chart in `FundamentalsPanel` (builds on A-1)
  - Unit tests with mocked CSV response
- **Todo:**
  1. Inspect OpenInsider CSV export format for a sample symbol (e.g. AAPL).
  2. Implement `OpenInsiderAdapter.get_recent_trades(symbol, days=90)` — fetch CSV, parse rows,
     return list of `InsiderTrade` dataclass objects.
  3. Add rate limit (1 req/sec) and Redis cache (TTL 6 hours) to avoid hammering.
  4. Wire into `GET /api/v1/fundamentals/{symbol}/insider-flow`.
  5. Display as sortable table in `FundamentalsPanel` → "Insiders" tab.
  6. Write unit tests.
- **Relevant Context:**
  - Scraping pattern: `backend/app/services/news/sec_edgar.py`
  - Rate limit pattern: `backend/app/services/crypto/coingecko.py` (`_TokenBucket`)

---

### A-3 · StockTwits Adapter

- **Status:** `[x] done`
- **Intent:** Pull social sentiment from StockTwits public API (free, no API key required for
  public stream). Returns recent messages with `bullish`/`bearish` sentiment tags. Feeds into
  `AIScorePanel` social sentiment component and `NewsFeedPanel`.
- **API:** `https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json` — no auth for basic
  stream (30 most recent messages).
- **Access tier needed:** Free (public endpoint).
- **Expected Outcomes:**
  - `StockTwitsAdapter` in `backend/app/services/news/stocktwits.py`
  - Methods: `get_stream(symbol)` → list of `{message, sentiment, created_at, username, likes}`
  - Sentiment ratio computed: bullish_count / total tagged messages → `bullish_pct` float
  - Wired into `GET /api/v1/news/{symbol}` aggregator response (new `source: "stocktwits"` items)
  - `bullish_pct` fed into `GET /api/v1/ml/ai-score` composite calculation
  - Unit tests
- **Todo:**
  1. Read `backend/app/services/news/aggregator.py` to understand how sources are merged.
  2. Implement `StockTwitsAdapter` with `_TokenBucket` (10 req/min to stay well inside limits).
  3. Add `STOCKTWITS_ACCESS_TOKEN` to config + `.env.example` (optional — only needed for
     write operations; read is unauthenticated).
  4. Wire into news aggregator.
  5. Update `GET /api/v1/ml/ai-score` to include StockTwits `bullish_pct` in composite score.
  6. Display StockTwits sentiment pill in `AIScorePanel`.
  7. Write unit tests.
- **Relevant Context:**
  - Aggregator: `backend/app/services/news/aggregator.py`
  - AI score endpoint: `backend/app/api/v1/ml.py`
  - Frontend: `frontend/components/panels/AIScorePanel/index.tsx`

---

### A-4 · EarningsCall.ai Adapter

- **Status:** `[x] done`
- **Intent:** Pull AI-summarized earnings call transcripts (sentiment, key topics, guidance
  language) from EarningsCall.ai API. Surfaces in `NewsFeedPanel` and `FundamentalsPanel`
  earnings tab.
- **API:** `https://earningscall.biz/api` — REST, JSON, API-key auth. Endpoints: transcripts,
  company list, annual/quarterly transcript lookup.
- **Access tier needed:** Free tier gives limited transcript access (recent quarters for major
  tickers). Implementation uses free tier only. When upgrading to Individual plan ($9/mo for
  1,000 transcripts/month), no code changes are needed — only a new API key.
- **Expected Outcomes:**
  - `EarningsCallAdapter` in `backend/app/services/news/earningscall.py`
  - Methods: `get_transcript(symbol, year, quarter)`, `get_recent_transcripts(symbol)`
  - AI summary (if returned by API) shown in `FundamentalsPanel` → "Earnings" tab
  - Falls back gracefully when key absent
  - Unit tests
- **Todo:**
  1. Add `EARNINGSCALL_API_KEY` to config + `.env.example`.
  2. Implement adapter with retry and graceful degradation on 402/403.
  3. Wire into `GET /api/v1/news/{symbol}` aggregator (source: "earningscall").
  4. Display in `FundamentalsPanel` Earnings tab — transcript summary cards.
  5. Write unit tests with mocked response.
- **Relevant Context:**
  - Pattern: `backend/app/services/news/benzinga.py`

---

### A-5 · Reuters / Refinitiv Elektron (Eikon) Adapter

- **Status:** `[x] done`
- **Intent:** Write ADR-009 documenting the integration path for Reuters/Refinitiv and deliver a
  fully wired adapter stub that activates the moment a license key is provided. No live API
  calls are made without a valid `REFINITIV_APP_KEY`. Reuters Eikon/Refinitiv data requires a
  paid Refinitiv Data Platform account (~$200/mo developer tier or Eikon desktop license). The
  adapter is scoped to news headlines and fundamental snapshots (not the full tick feed). The
  code will be complete and testable via mocks; enabling it in production requires only adding
  the env var.
- **API:** `refinitiv-data` Python SDK → REST-based cloud gateway.
- **Access tier needed:** None required to build or test. Refinitiv Data Platform license
  (~$200/mo) required to activate in production. No code changes needed at that point —
  set `REFINITIV_APP_KEY` and the adapter activates automatically.
- **Expected Outcomes:**
  - ADR-009 written at `docs/adr/ADR-009-reuters-refinitiv.md` documenting license options,
    costs, integration approach, and activation instructions for when a license is purchased
  - `RefinitivAdapter` stub in `backend/app/services/news/refinitiv.py` — fully implemented
    but feature-flagged (skipped gracefully when `REFINITIV_APP_KEY` is absent)
  - Methods: `get_news_headlines(symbol, count=20)`, `get_fundamental_snapshot(symbol)`
  - `refinitiv-data` added as an optional dependency in `pyproject.toml` extras
    (`pip install quantnexus[refinitiv]`)
  - Wired into news aggregator (source: "reuters") — silently omitted when key absent
  - Unit tests using mocked SDK responses (run without a real license)
  - `.env.example` documents `REFINITIV_APP_KEY` with a comment pointing to license purchase URL
- **Todo:**
  1. Write ADR-009 documenting Refinitiv license options and activation path.
  2. Add `REFINITIV_APP_KEY` to `backend/app/core/config.py` (optional, default `None`) and
     `.env.example` with a comment: `# Get a license at https://developers.refinitiv.com`.
  3. Add `refinitiv-data>=1.0.0` as optional dependency in `pyproject.toml`.
  4. Implement `RefinitivAdapter` with `try/import` guard (graceful skip if SDK not installed).
  5. Wire into news aggregator with feature-flag guard.
  6. Write unit tests with mocked SDK responses.
- **Relevant Context:**
  - ADR format: `docs/adr/ADR-008-pytorch-lstm.md`
  - Feature-flag pattern: same as how `OANDA_API_KEY` is present but adapter unimplemented

---

### A-6 · OANDA Forex Adapter

- **Status:** `[x] done`
- **Intent:** `OANDA_API_KEY` and `OANDA_ACCOUNT_ID` are already in `.env.example` with
  `OANDA_BASE_URL=https://api-fxpractice.oanda.com` but the adapter was never written. OANDA
  provides a free practice account with full REST API access. This unlocks forex pairs
  (EUR/USD, GBP/JPY, etc.) in the chart, watchlist, and screener.
- **API:** `https://api-fxpractice.oanda.com/v3` — REST, Bearer token auth, SSE streaming.
- **Access tier needed:** Free practice account.
- **Expected Outcomes:**
  - `OANDAProvider` implementing `MarketDataProvider` base in
    `backend/app/services/market_data/oanda.py`
  - Methods: `get_bars()`, `get_quote()`, `get_quotes()`, `stream_quotes()` + `search_symbols()`
  - Registered in `backend/app/services/market_data/router.py` as `"oanda"` provider
  - `MARKET_DATA_PROVIDER=oanda` selects it; also used as fallback for forex pairs when Alpaca
    returns no data
  - Live streaming via OANDA SSE pricing stream
  - Unit tests
- **Todo:**
  1. Read `backend/app/services/market_data/base.py` for canonical schemas.
  2. Read `backend/app/services/market_data/alpaca.py` for WebSocket streaming pattern.
  3. Implement `OANDAProvider` with REST bars + SSE streaming.
  4. Register in `router.py`.
  5. Update `MARKET_DATA_PROVIDER` accepted values in `config.py`.
  6. Write unit tests.
- **Relevant Context:**
  - Base class: `backend/app/services/market_data/base.py`
  - Reference implementation: `backend/app/services/market_data/alpaca.py`

---

### A-7 · Morningstar / FactSet / Capital IQ / PitchBook — Research & Integration Assessment

- **Status:** `[x] done`
- **Intent:** These are institutional data vendors with no public free-tier API. This sub-task
  is a **documented integration assessment**, not a code sprint. The outcome is a decision record
  (ADR-010) plus stub adapters that can be activated when a data license is acquired.
- **Vendors and access reality:**
  - **Morningstar:** Morningstar Direct has an unofficial Python library (`morningstar-data`).
    Official API requires an enterprise data license (~$10k+/yr). Free alternative: `yfinance`
    returns Morningstar sector/industry classifications.
  - **FactSet:** FactSet Open:FactSet API has a free developer tier (500 req/day) with coverage
    on fundamentals, ownership, estimates. SDK: `fds.sdk.FactSetFundamentals`.
  - **Capital IQ (S&P Global):** No public API. Requires an S&P Global Market Intelligence
    enterprise license. Data available via Excel plugin only — no programmatic access without
    enterprise agreement.
  - **PitchBook:** Private company data only. No public API. Requires enterprise license.
  - **eMoney:** Financial planning platform (not a market data API) — not relevant for trading
    platform integration.
  - **Bloomberg Terminal:** See sub-task A-8.
- **Expected Outcomes:**
  - ADR-010 written at `docs/adr/ADR-010-institutional-data-vendors.md` documenting each
    vendor's access reality, cost tier, and integration feasibility
  - `FactSetAdapter` stub in `backend/app/services/fundamentals/factset.py` — uses the free
    FactSet Open API developer tier for fundamentals + ownership data
  - `FactSet_API_KEY` added to config + `.env.example`
  - Stubs for Morningstar (falls back to yfinance sector data), Capital IQ (blocked), PitchBook
    (blocked) documented in ADR with deferral rationale
- **Todo:**
  1. Research FactSet Open:FactSet free developer tier — confirm endpoints, rate limits.
  2. Write ADR-010 covering all five vendors.
  3. Implement `FactSetAdapter` for fundamentals: `get_financials()`, `get_estimates()`,
     `get_ownership()`.
  4. Add `FACTSET_API_KEY` to config + `.env.example`.
  5. Wire into `GET /api/v1/fundamentals/{symbol}` as optional secondary source.
  6. Write unit tests.
- **Relevant Context:**
  - ADR format: `docs/adr/ADR-008-pytorch-lstm.md`

---

### A-8 · Bloomberg Terminal / AlphaSpace Integration Assessment

- **Status:** `[x] done`
- **Intent:** Assess realistic integration paths for Bloomberg and AlphaSpace and write a
  documented decision record (ADR-011). No free API exists for Bloomberg; however, the Bloomberg
  Open Symbology (FIGI) API is free and useful for cross-referencing identifiers across data
  vendors. AlphaSpace is a quantitative factor research platform — its API provides factor
  exposure data.
- **Bloomberg reality:**
  - **Bloomberg Terminal:** Requires a Terminal subscription (~$24k/yr per seat). Data accessible
    via `blpapi` Python SDK only when a Terminal or B-PIPE server license is present. Not viable
    for general platform use.
  - **Bloomberg Open Symbology (OpenFIGI):** Free REST API for financial instrument ID mapping
    (ticker → FIGI, ISIN, CUSIP). Genuinely useful for cross-referencing data vendors.
  - **Bloomberg Enterprise Access Point (EAP):** Cloud-based data delivery. Requires enterprise
    agreement.
- **AlphaSpace reality:**
  - AlphaSpace provides quantitative factor analytics. API requires subscription. Worth integrating
    if the platform targets quant researchers.
- **Expected Outcomes:**
  - ADR-011 written at `docs/adr/ADR-011-bloomberg-alphaspace.md`
  - `OpenFIGIAdapter` implemented in `backend/app/services/fundamentals/openfigi.py` — free,
    useful for symbol lookup across vendors
  - `OPENFIGI_API_KEY` added to config + `.env.example` (optional — unauthenticated tier allows
    10 req/min; authenticated 25 req/min)
  - Bloomberg Terminal adapter stub documented in ADR as deferred (requires Terminal license)
  - AlphaSpace adapter stub documented in ADR as deferred (requires subscription)
- **Todo:**
  1. Write ADR-011.
  2. Implement `OpenFIGIAdapter` with `map_identifiers(ticker, exchange)` → returns FIGI, ISIN,
     CUSIP for cross-referencing.
  3. Add `OPENFIGI_API_KEY` to config + `.env.example`.
  4. Wire OpenFIGI into symbol search (`GET /api/v1/market/search`) to enrich results with FIGI
     identifier.
  5. Write unit tests.

---

## Track B — Deferred Chart Types and Drawing Tools

### B-1 · Point & Figure and Kagi Chart Types

- **Status:** `[ ] pending`
- **Intent:** These chart types have no time axis — price is the only axis. They are fundamentally
  incompatible with lightweight-charts' `TimeScale`. The plan is to render them on a custom HTML
  Canvas overlay positioned over the existing chart panel, with the lightweight-charts instance
  hidden when P&F or Kagi mode is active. This is the minimal viable approach without replacing
  the chart library.
- **Expected Outcomes:**
  - `PointAndFigureChart` React component using HTML Canvas (`<canvas>` element)
  - `KagiChart` React component using HTML Canvas
  - `ChartTypeSelector` in `ChartPanel` toolbar — new options: "Candlestick" (default), "P&F",
    "Kagi" alongside existing Line/Bar/Area
  - When P&F or Kagi selected: lightweight-charts instance visibility `hidden`; canvas overlay
    `visible`
  - P&F uses standard box-size / reversal parameters (default: ATR-based box size, 3-box reversal)
  - Kagi uses standard reversal threshold (default: 1% or ATR-based)
  - Both use existing OHLCV data already loaded in `ChartPanel` state — no new API calls
  - Vitest unit tests for P&F / Kagi calculation logic
- **Todo:**
  1. Read `frontend/components/panels/ChartPanel/index.tsx` and `ChartCanvas.tsx` for the
     component tree and data flow.
  2. Implement `pointAndFigure(bars, boxSize, reversalBoxes)` calculation function in
     `frontend/lib/indicators/chartTypes.ts`.
  3. Implement `kagi(bars, reversalThreshold)` calculation function in same file.
  4. Build `PointAndFigureCanvas` component: renders X/O columns on canvas.
  5. Build `KagiCanvas` component: renders rising/falling Kagi lines.
  6. Add type selector to `ChartToolbar.tsx` — toggle between lightweight-charts and canvas.
  7. Handle resize observer for canvas sizing.
  8. Write unit tests for calculation functions.
- **Relevant Context:**
  - Current chart: `frontend/components/panels/ChartPanel/ChartCanvas.tsx`
  - Drawing tool pattern: `frontend/components/panels/ChartPanel/useFibonacciTool.ts`

---

### B-2 · Gann Fan Drawing Tool

- **Status:** `[ ] pending`
- **Intent:** Gann Fan is a 3-click drawing tool that emanates 9 fan lines at fixed Gann angles
  (1×8, 1×4, 1×3, 1×2, 1×1, 2×1, 3×1, 4×1, 8×1) from a pivot point. Unlike Elliott Wave
  (which requires wave detection logic), Gann Fan is purely geometric — a good candidate for
  implementation now.
- **Expected Outcomes:**
  - `useGannFanTool` hook in
    `frontend/components/panels/ChartPanel/useGannFanTool.ts`
  - 2-click interaction: click 1 = pivot point (price + time); click 2 = reference point that
    sets the 1×1 angle scale
  - 9 fan lines drawn as lightweight-charts `LineSeries` objects extending rightward
  - Fan line labels at right edge of chart: "1×1", "2×1", etc.
  - Persisted to workspace (same JSON serialization as Fibonacci / Trendline)
  - Vitest tests for angle calculation
- **Todo:**
  1. Read `frontend/components/panels/ChartPanel/useFibonacciTool.ts` and
     `usePitchforkTool.ts` for the 2-click / 3-click interaction patterns.
  2. Read `frontend/components/panels/ChartPanel/ChartCanvas.tsx` for how tools register and
     serialize to workspace.
  3. Implement `useGannFanTool` with angle math.
  4. Add "Gann Fan" to drawing tool selector in `ChartToolbar.tsx`.
  5. Write tests for angle computation.
- **Relevant Context:**
  - Existing tools: `useFibonacciTool.ts`, `useTrendlineTool.ts`, `usePitchforkTool.ts`,
    `useAnnotationTool.ts`

---

### B-3 · Elliott Wave Drawing Tool (Manual Labeling)

- **Status:** `[ ] pending`
- **Intent:** Implement manual Elliott Wave labeling (not automated detection — that requires ML
  wave detection which is out of scope). The tool allows the user to click wave pivots and
  assigns wave labels (1, 2, 3, 4, 5, A, B, C) in sequence. Lines connect the pivots.
  Labels are rendered at each pivot. This is interaction-heavy but geometrically straightforward.
- **Expected Outcomes:**
  - `useElliottWaveTool` hook in
    `frontend/components/panels/ChartPanel/useElliottWaveTool.ts`
  - Multi-click tool: each click places the next wave label in the sequence
  - Double-click or Escape ends the current wave count
  - Wave degree selector: Primary (1–5), Intermediate (circled), Minor (lower case)
  - Lines connect consecutive pivots; labels anchored above/below based on wave direction
  - Persisted to workspace
  - Vitest tests for label sequencing
- **Todo:**
  1. Read `usePitchforkTool.ts` for the multi-click interaction pattern.
  2. Define wave label sequence state machine (impulse: 1→2→3→4→5; corrective: A→B→C).
  3. Implement `useElliottWaveTool`.
  4. Add "Elliott Wave" to drawing tool selector.
  5. Write unit tests for label state machine.
- **Relevant Context:**
  - Most complex drawing tool — plan for ~2× effort vs Gann Fan

---

## Track C — Twitter/X and Seeking Alpha

### C-1 · Twitter/X News Adapter

- **Status:** `[x] done`
- **Intent:** The X API v2 Basic tier ($100/month) has been deferred due to cost. The revised
  approach is to target the **Free tier** (`TWITTER_BEARER_TOKEN` already in `.env.example`)
  which allows 500k tweet reads/month and 1 app-only read request per 15-minute window.
  This is enough for a low-frequency sentiment batch job (not real-time).
- **Access tier needed:** Free tier (Bearer token only). `TWITTER_BEARER_TOKEN` already in config.
- **Expected Outcomes:**
  - `TwitterAdapter` in `backend/app/services/news/twitter.py`
  - Uses `tweepy` v4 library (already a candidate dependency) with Bearer token auth
  - `get_cashtag_tweets(symbol, max_results=10)` — searches `$AAPL` cashtag, last 7 days
  - Returns `{text, created_at, public_metrics, sentiment}` list
  - Rate-limited to 1 request per 15 minutes per cashtag (respects free tier window)
  - Results cached in Redis for 15 minutes
  - Wired into news aggregator (source: "twitter") and AIScorePanel
  - Unit tests with mocked Tweepy responses
- **Todo:**
  1. Add `tweepy>=4.14.0` to `backend/requirements.txt`.
  2. Add `TWITTER_BEARER_TOKEN` to `config.py` (already in `.env.example`).
  3. Implement `TwitterAdapter` with 15-minute rate-limit enforcement.
  4. Wire into news aggregator.
  5. Write unit tests.
- **Relevant Context:**
  - `TWITTER_BEARER_TOKEN` already in `.env.example` line 73
  - Rate limit pattern: `backend/app/services/crypto/coingecko.py`

---

### C-2 · Seeking Alpha Alternative — Motley Fool / Yahoo Finance Editorial Feed

- **Status:** `[x] done`
- **Intent:** Seeking Alpha has no public API and scraping violates ToS. The alternative is to
  use Yahoo Finance's editorial feed (free, `yfinance` library exposes `Ticker.news`) which
  returns Yahoo Finance + Motley Fool editorial headlines. This is effectively the "Seeking
  Alpha alternative" that requires no ToS violation and no cost.
- **Expected Outcomes:**
  - `YahooNewsAdapter` in `backend/app/services/news/yahoo_news.py`
  - `get_articles(symbol)` — calls `yf.Ticker(symbol).news` → returns last 20 articles
  - Wired into news aggregator (source: "yahoo_finance")
  - Unit tests
- **Todo:**
  1. Implement `YahooNewsAdapter` using existing `yfinance` library (already a dependency).
  2. Wire into `backend/app/services/news/aggregator.py`.
  3. Write unit tests.
- **Relevant Context:**
  - `yfinance` already used in `backend/app/services/market_data/yahoo_finance.py`
  - Zero new dependencies required

---

## Track D — Live Order Routing (Real Brokerage)

### D-1 · OANDA Live Forex Order Routing

- **Status:** `[ ] pending`
- **Intent:** Wire the `OANDAProvider` (built in A-6) into the orders API for live forex trading
  on OANDA practice accounts. This is the minimal "live" order routing expansion — OANDA
  practice accounts are free and require no legal review. Real-money routing deferred.
- **Expected Outcomes:**
  - `OANDAOrderService` in `backend/app/services/orders/oanda.py`
  - Supports: market order, limit order, stop order, order cancellation, position close
  - Wired into `POST /api/v1/orders` — when symbol is a forex pair (e.g. EUR_USD), routes to
    OANDA instead of Alpaca
  - Order fill events published to WebSocket (`/ws/orders`)
  - `OrderEntryPanel` detects forex pairs and sets correct lot size / pip display
  - Unit tests
- **Todo:**
  1. Read `backend/app/services/orders/` to understand existing Alpaca order routing.
  2. Implement `OANDAOrderService` with practice API endpoints.
  3. Add routing logic: forex pair detection → OANDA; equities → Alpaca.
  4. Wire fill events to existing fill task machinery.
  5. Write unit tests.
- **Relevant Context:**
  - Depends on: A-6 (OANDAProvider)
  - Existing: `backend/app/services/orders/` (Alpaca routing)

---

### D-2 · Risk Management Kill-Switch

- **Status:** `[ ] pending`
- **Intent:** A documented requirement for real-money order routing. Implements a platform-wide
  kill-switch that halts all new order submissions (but does not cancel existing orders — that
  requires broker-side cancel-all which is broker-specific). Controlled by a Redis flag; toggled
  via admin API endpoint.
- **Expected Outcomes:**
  - `TRADING_KILL_SWITCH` Redis key: `1` = halted, `0` or absent = active
  - Middleware check in `POST /api/v1/orders` — if kill-switch active, return HTTP 503 with
    `{"error": "Trading halted by kill-switch"}`
  - `POST /api/v1/admin/kill-switch` endpoint (admin-only JWT role) to toggle
  - Kill-switch status shown in `OrderEntryPanel` header bar (red banner when active)
  - Unit tests for middleware behavior
- **Todo:**
  1. Add `TRADING_KILL_SWITCH` Redis check to `backend/app/api/v1/orders.py`.
  2. Create `backend/app/api/v1/admin.py` with kill-switch toggle endpoint (admin role guard).
  3. Update `OrderEntryPanel` to poll kill-switch status and show red banner.
  4. Write unit tests.

---

## Track E — MLOps Pipeline and Advanced ML

### E-1 · MLflow Experiment Tracking

- **Status:** `[ ] pending`
- **Intent:** Fill `ml/experiments/` with a real MLflow tracking setup. Each Celery training task
  logs parameters, metrics, and artifacts to MLflow. This establishes baselines before any model
  improvement work begins. MLflow open-source server runs as a new Docker service.
- **Expected Outcomes:**
  - `mlflow` added to `backend/requirements.txt`
  - `MLFLOW_TRACKING_URI` env var added to config + `.env.example`
  - `ml/experiments/mlflow_config.py` — tracking URI + experiment name helpers
  - Each training task (`train_lstm_task`, `train_xgboost_task`, `train_hmm_task`) wrapped with
    `mlflow.start_run()` — logs hyperparams, train/val loss, accuracy, and model artifact
  - MLflow service added to `docker-compose.yml` (official `ghcr.io/mlflow/mlflow` image)
    **Note:** This image is from GitHub Container Registry (ghcr.io), not docker.io. Per security
    rules, public container images should be sourced from Red Hat's registry. Evaluate using a
    UBI-based custom MLflow image or document a security exception for this service.
  - `ml/experiments/` populated with experiment configs and example notebooks
  - Unit tests for logging helper functions
- **Todo:**
  1. Add `mlflow>=2.14.0` to `backend/requirements.txt`.
  2. Add `MLFLOW_TRACKING_URI=http://localhost:5001` to config + `.env.example`.
  3. Write `ml/experiments/mlflow_config.py`.
  4. Wrap `ml_tasks.py` training tasks with MLflow run logging.
  5. Add MLflow service to `docker-compose.yml` (document container image security decision).
  6. Write unit tests for helper functions.
- **Relevant Context:**
  - Training tasks: `backend/app/tasks/ml_tasks.py`
  - ML models: `ml/models/lstm/train.py`, `ml/models/xgboost/model.py`, `ml/models/hmm/train.py`

---

### E-2 · Feature Store (Redis + TimescaleDB)

- **Status:** `[ ] pending`
- **Intent:** Fill `ml/feature_store/`. The feature store is not a new infrastructure service
  (Feast, Tecton) — it is a lightweight feature computation + caching layer. Pre-computed
  features for the last N bars are stored in Redis (online store) and TimescaleDB (offline store)
  so training tasks read from the feature store instead of recomputing indicators on every run.
- **Expected Outcomes:**
  - `ml/feature_store/__init__.py` and `ml/feature_store/features.py`
  - `FeatureStore` class: `compute_and_cache(symbol, bars)` writes feature vectors to Redis
    (TTL 5 minutes) and TimescaleDB `feature_vectors` hypertable
  - `FeatureStore.get(symbol, lookback)` reads from Redis (if warm) else TimescaleDB
  - All three model training tasks updated to use `FeatureStore.get()` instead of recomputing
  - New Alembic migration for `feature_vectors` hypertable
    (columns: time, symbol, feature_name, value)
  - Unit tests
- **Todo:**
  1. Read `ml/models/lstm/dataset.py` — `build_features()` — to understand current feature
     computation.
  2. Design `feature_vectors` TimescaleDB schema.
  3. Implement `FeatureStore` class.
  4. Update all three training tasks to use the store.
  5. Write Alembic migration.
  6. Write unit tests.

---

### E-3 · Model Registry and Versioning

- **Status:** `[ ] pending`
- **Intent:** Fill `ml/serving/`. Today model weights are flat files in `data/ml_weights/`.
  The registry tracks which version of each model is deployed (champion), stores previous
  versions (challenger), and supports A/B testing by routing a fraction of `/ml/predict`
  requests to the challenger. Uses MLflow Model Registry (built on top of E-1).
- **Expected Outcomes:**
  - `ml/serving/registry.py` — `ModelRegistry` class wrapping MLflow Model Registry API
  - `ModelRegistry.promote(symbol, model_type, run_id)` — promotes a run to "Production" stage
  - `ModelRegistry.get_production_model(symbol, model_type)` — loads champion model weights
  - `ModelRegistry.ab_test(symbol, model_type, challenger_run_id, traffic_pct=0.1)` — routes
    10% of inference requests to challenger
  - `GET /api/v1/ml/registry` endpoint listing registered models + their production version
  - `POST /api/v1/ml/registry/{symbol}/{model_type}/promote` endpoint
  - Unit tests
- **Todo:**
  1. Read `backend/app/api/v1/ml.py` for current predict endpoints.
  2. Implement `ModelRegistry` using MLflow registry API.
  3. Update `GET /ml/lstm/predict` and `GET /ml/xgboost/predict` to load via registry instead
     of raw file path.
  4. Add registry endpoints to `ml.py` router.
  5. Write unit tests.
- **Relevant Context:**
  - Depends on: E-1 (MLflow tracking must be set up first)

---

### E-4 · Transformer / Attention-Based Model

- **Status:** `[ ] pending`
- **Intent:** Fill `ml/models/transformer/`. Per ADR-005, the original re-engagement criteria
  required 30+ days of live tick data. Since the platform may not yet have accumulated that
  volume, this sub-task proceeds in **two phases**:
  - **Phase 1 (always):** Implement the full TFT model, dataset, training loop, and API
    endpoints using the existing OHLCV bars data (which is available now). This proves the
    architecture works end-to-end.
  - **Phase 2 (gated):** Switch the dataset to use tick-resolution features once 30+ days of
    tick data is confirmed in the `ticks` hypertable. This is a dataset swap, not a model
    rewrite. The gate check is a single SQL query before Phase 2 starts.
  Uses a Temporal Fusion Transformer (TFT) architecture — proven on financial time series.
- **GPU note:** Training works on CPU (slow but functional). Apple Silicon MPS acceleration
  is supported by PyTorch natively. Cloud GPU is optional for production retraining jobs.
- **Expected Outcomes:**
  - `ml/models/transformer/model.py` — `TemporalFusionTransformer` PyTorch class
  - `ml/models/transformer/dataset.py` — multi-variate sequence dataset (Phase 1: OHLCV bars;
    Phase 2: tick features once data is available)
  - `ml/models/transformer/train.py` — training loop with configurable data source
  - Celery task `train_transformer_task` in `ml_tasks.py`
  - `POST /api/v1/ml/transformer/train` and `GET /api/v1/ml/transformer/predict` endpoints
  - TFT confidence interval output (quantile regression) surfaced in `AIScorePanel`
  - ADR-005 updated: Phase 1 unblocked; Phase 2 gated on tick data volume
  - Unit tests
- **Todo:**
  1. Add `pytorch-forecasting>=1.1.0` to `backend/requirements.txt`.
  2. Implement `TemporalFusionTransformer` using OHLCV bars as input (Phase 1).
  3. Implement training loop and Celery task.
  4. Add `POST /api/v1/ml/transformer/train` and `GET /api/v1/ml/transformer/predict`.
  5. Surface TFT prediction interval in `AIScorePanel`.
  6. Update ADR-005 to document the two-phase approach.
  7. Write unit tests.
  8. *(Phase 2 gate)* Once tick volume confirmed, update `dataset.py` to use tick features.
- **Relevant Context:**
  - ADR-005: `docs/adr/ADR-005-transformer-deferral.md`
  - Existing LSTM: `ml/models/lstm/model.py` (architecture to extend from)
  - Phase 2 gate query: `SELECT COUNT(*), MIN(time), MAX(time) FROM ticks WHERE symbol='AAPL'`

---

## Track F — C++ Execution Engine (Long Horizon)

### F-1 · C++ Engine Scaffolding and Python Bridge

- **Status:** `[ ] pending`
- **Intent:** The `engine/` directory is empty. This sub-task creates the project scaffolding:
  CMakeLists.txt, directory structure, pybind11 bridge stub, and a minimal "echo order"
  implementation that proves the build pipeline works end-to-end. No FIX protocol yet.
- **Expected Outcomes:**
  - `engine/CMakeLists.txt` — CMake 3.20+ build with C++17 standard
  - `engine/src/` — core source files
  - `engine/include/` — header files
  - `engine/bindings/` — pybind11 Python module
  - `engine/tests/` — Google Test unit tests
  - Minimal `OrderRouter` class: accepts an `Order` struct, logs it, returns `OrderAck`
  - Python bridge `engine_bridge` module: `submit_order(symbol, side, qty, price)` → `OrderAck`
  - `engine/README.md` updated with build instructions
  - CI step in `.github/workflows/ci.yml` to build + run engine tests (conditional on
    cmake being available)
  - Re-engagement criteria documented: this step does NOT require live brokerage connectivity —
    it establishes the build system only
- **Todo:**
  1. Read `engine/README.md` for current architecture vision.
  2. Create CMakeLists.txt with pybind11 FetchContent.
  3. Implement `Order`, `OrderAck` structs and minimal `OrderRouter` class.
  4. Implement pybind11 bindings.
  5. Write Google Test unit test for order echo.
  6. Add CI build step.
  7. Update `engine/README.md` with build instructions.
- **Relevant Context:**
  - `engine/README.md` — architecture vision
  - pybind11 preferred over ctypes for type safety

---

### F-2 · Lock-Free Order Book (C++)

- **Status:** `[ ] pending`
- **Intent:** Implement a lock-free in-memory order book data structure in C++. This is the
  core data structure that makes the C++ engine worth building — it enables microsecond-latency
  book updates vs. the Python dict-based order book currently in `backend/app/services/`.
- **Expected Outcomes:**
  - `engine/src/order_book.hpp` / `engine/src/order_book.cpp` — `LockFreeOrderBook` class
  - Supports: add limit order, cancel order, get best bid/ask, snapshot (top N levels)
  - Uses `std::atomic` for lock-free price level maps; price buckets use `std::map<Price, Level>`
  - Exposed via pybind11: `OrderBook.add(side, price, qty)`, `OrderBook.cancel(id)`,
    `OrderBook.snapshot(depth)` → returns dict
  - Python integration test: populate book with 1000 orders, verify snapshot
  - Benchmark in README: target < 1μs per add/cancel
- **Todo:**
  1. Design price level data structure (price → deque of orders).
  2. Implement `LockFreeOrderBook` with `std::atomic` counters.
  3. Add pybind11 bindings.
  4. Write Google Test unit tests.
  5. Write Python integration test.
  6. Add latency benchmark.
- **Relevant Context:**
  - Depends on: F-1 (build system must exist first)

---

### F-3 · FIX Protocol Integration (QuickFIX/n)

- **Status:** `[ ] pending`
- **Intent:** Integrate QuickFIX/n (C++ FIX library) into the engine for institutional order
  routing. Requires institutional brokerage relationships and compliance review — implementation
  is the adapter/stub only; live connectivity is not the goal of this sub-task.
- **Pre-condition:** Legal/compliance review complete. This sub-task implements the FIX session
  handler and message codec; live brokerage routing to real money accounts requires a separate
  approval process outside this plan.
- **Expected Outcomes:**
  - `engine/src/fix/` — FIX session handler, message builder, execution report handler
  - QuickFIX/n added as CMake FetchContent dependency
  - `FIXAdapter` class: `send_new_order_single()`, `send_cancel_request()`,
    `on_execution_report()` callback
  - Simulator mode: FIX messages logged to file; no live broker connectivity required for tests
  - Python bridge: `engine_bridge.fix_submit(order)`, `engine_bridge.fix_cancel(clordid)`
  - Integration test using QuickFIX simulator counterparty
- **Todo:**
  1. Add QuickFIX/n as CMake FetchContent dependency.
  2. Implement FIX 4.2 session handler (most brokers use 4.2 or 5.0SP2).
  3. Implement `NewOrderSingle`, `OrderCancelRequest`, `ExecutionReport` handlers.
  4. Add pybind11 bindings.
  5. Write integration test with simulator counterparty.
- **Relevant Context:**
  - Depends on: F-1, F-2
  - Legal pre-condition must be documented before live connectivity work begins

---

## Appendix: Sequencing and Dependencies

```
Track A (Data):   A-1 → A-2 → A-3 → A-4 → A-5 → A-6 → A-7 → A-8
                  (A-2 depends on A-1 FundamentalsPanel; others independent)

Track B (Charts): B-1 → B-2 → B-3
                  (B-2 and B-3 independent; B-1 self-contained)

Track C (News):   C-1 independent; C-2 independent

Track D (Orders): A-6 must precede D-1; D-2 independent (risk infra)

Track E (MLOps):  E-1 → E-2 → E-3 → E-4
                  (E-3 depends on E-1; E-4 requires 30+ days tick data)

Track F (C++):    F-1 → F-2 → F-3
                  (strictly sequential; F-3 has legal pre-condition)

Cross-track:      A-3 (StockTwits) enriches E (AI score inputs)
                  A-1 (FMP) data feeds E-2 (feature store fundamentals)
                  D-2 (kill-switch) must precede any real-money D routing
                  E must be complete before F begins
```

---

## Appendix: New Environment Variables Required

| Variable | Track | Purpose |
|----------|-------|---------|
| `FMP_API_KEY` | A-1 | Financial Modeling Prep |
| `FACTSET_API_KEY` | A-7 | FactSet Open API |
| `EARNINGSCALL_API_KEY` | A-4 | EarningsCall.ai |
| `REFINITIV_APP_KEY` | A-5 | Refinitiv/Reuters (optional) |
| `STOCKTWITS_ACCESS_TOKEN` | A-3 | StockTwits (optional for reads) |
| `OPENFIGI_API_KEY` | A-8 | OpenFIGI (optional) |
| `MLFLOW_TRACKING_URI` | E-1 | MLflow server |
| `TRADING_KILL_SWITCH` | D-2 | Redis key (not an API key) |

Variables already in `.env.example` that unlock new adapters in this plan:
- `OANDA_API_KEY` / `OANDA_ACCOUNT_ID` → A-6, D-1
- `TWITTER_BEARER_TOKEN` → C-1

---

## Appendix: New ADRs Required

| ADR | Track | Title |
|-----|-------|-------|
| ADR-009 | A-5 | Reuters / Refinitiv Elektron — License Options and Activation Path |
| ADR-010 | A-7 | Institutional Data Vendor Assessment (Morningstar, FactSet, Capital IQ, PitchBook, eMoney) |
| ADR-011 | A-8 | Bloomberg Terminal and AlphaSpace Integration Assessment |
| ADR-012 | E-4 | Temporal Fusion Transformer Architecture Selection |
| ADR-013 | F-1 | C++ Engine Technology Choices (CMake, pybind11, QuickFIX/n) |

---

## Implementation Complete — Final Status (2025-07-15)

All 23 Tier 4 work items are now fully implemented.

### Backend Test Count Progress

| Milestone | Tests Passing |
|-----------|--------------|
| Tier 1–3 baseline | 259 |
| After Tracks A–C (prior session) | 259 |
| After D-1 + D-2 (kill-switch + OANDA orders) | 280 |
| After Track E (MLOps: MLflow, feature store, registry, TFT) | 308 |
| After Track F (C++ engine Python bridge stubs) | 330 |

### New Files Delivered This Session

#### Track D — OANDA Forex Orders + Kill-Switch
| File | Description |
|------|-------------|
| `backend/app/services/orders/oanda_order_service.py` | OANDA forex order placement, cancel, list |
| `backend/app/services/kill_switch.py` | Redis-backed platform kill-switch service |
| `backend/app/api/v1/forex_orders.py` | `POST/GET/DELETE /api/v1/orders/forex` |
| `backend/app/api/v1/admin.py` | Admin kill-switch toggle endpoints |
| `backend/app/config.py` | Added `admin_emails: list[str]` |
| `backend/app/api/v1/orders.py` | Kill-switch guard on `POST /api/v1/orders` |
| `backend/app/api/v1/router.py` | Registered `forex_orders` + `admin` routes |
| `backend/tests/unit/test_d1_d2_orders.py` | 21 tests (D-1/D-2) |

#### Track E — MLOps Pipeline
| File | Description |
|------|-------------|
| `ml/experiments/__init__.py` | Package init |
| `ml/experiments/tracker.py` | `ExperimentTracker` — MLflow wrapper (fail-open) |
| `ml/feature_store/__init__.py` | Package init |
| `ml/feature_store/store.py` | `FeatureStore` + `compute_features` (12 features, 2-level cache) |
| `ml/training/__init__.py` | Package init |
| `ml/training/registry.py` | `ModelRegistry` — filesystem + MLflow versioning |
| `ml/models/transformer/__init__.py` | Package init |
| `ml/models/transformer/model.py` | `TFTModel` — Temporal Fusion Transformer |
| `ml/models/transformer/train.py` | TFT training script with MLflow + registry integration |
| `ml/models/lstm/train.py` | Updated to use `ExperimentTracker` + `ModelRegistry` |
| `backend/app/tasks/ml_tasks.py` | Added `train_transformer_task` Celery task |
| `backend/app/api/v1/ml.py` | Added `/transformer/train`, `/transformer/predict`, `/registry` |
| `backend/tests/unit/test_track_e_mlops.py` | 28 tests (E-1 through E-4) |

#### Track F — C++ Execution Engine
| File | Description |
|------|-------------|
| `engine/CMakeLists.txt` | CMake 3.21+ build with pybind11 + GTest |
| `engine/include/order_book.h` | Lock-free L2 order book interface (`shared_mutex` phase 1) |
| `engine/include/risk_manager.h` | Pre-trade risk check interface (5 checks, < 500ns) |
| `engine/include/order_manager.h` | Order lifecycle + kill-switch interface |
| `engine/src/order_book.cpp` | Order book implementation |
| `engine/src/risk_manager.cpp` | Risk manager implementation |
| `engine/src/order_manager.cpp` | Order manager implementation |
| `engine/src/python_bridge.cpp` | pybind11 bindings (OrderBook, RiskManager, OrderManager) |
| `engine/fix/fix_session.h` | Abstract FIX session interface + `FixSessionSimulated` |
| `engine/fix/fix_session_simulated.cpp` | Simulated FIX fills (no live broker needed) |
| `engine/python/engine_bridge.py` | Pure-Python fallback stubs (C++ interface contract) |
| `engine/tests/test_order_book.cpp` | 8 GTest tests |
| `engine/tests/test_order_manager.cpp` | 10 GTest tests |
| `engine/tests/test_risk_manager.cpp` | 10 GTest tests |
| `engine/tests/CMakeLists.txt` | GTest via FetchContent |
| `engine/scripts/build_engine.sh` | Build script (requires cmake + pybind11) |
| `docs/adr/ADR-012-fix-protocol.md` | FIX re-engagement criteria and architecture |
| `docs/adr/ADR-013-cpp-engine.md` | C++ engine phased rollout and technology choices |
| `backend/tests/unit/test_track_f_engine.py` | 22 tests against Python fallback stubs |

### Build Instructions for C++ Engine

```bash
# Prerequisites (install once)
brew install cmake pybind11

# Build
./engine/scripts/build_engine.sh

# Run C++ unit tests
./engine/scripts/build_engine.sh test

# Use from Python
export ENGINE_BUILD_DIR="$(pwd)/engine/build"
python -c "import quantnexus_engine; print(quantnexus_engine.__doc__)"
```

---

