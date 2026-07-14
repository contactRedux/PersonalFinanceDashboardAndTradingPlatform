# Enterprise Algorithmic Trading Platform — Technical Plan

## Confirmed Scope Decisions

| Decision | Resolution |
|---|---|
| Execution engine | **Deferred** — front-end dashboard + data visualization only |
| Asset classes | All: equities, crypto, forex, futures, options |
| Data APIs | Documented per-component; final selection deferred to implementation |
| Front-end framework | **Next.js 15 (App Router)** |
| Back-end data service | **FastAPI (Python)** — strict separation from front-end |
| Panel build priority | Core trading panels first, then secondary panels, then advanced |
| Sub-tasks | **All 11 proceed** — no deferrals |
| Authentication | **Full enterprise auth from Phase 1** — JWT + refresh rotation + TOTP 2FA + RBAC |
| Indicator computation | **Both layers** — client-side TypeScript for real-time chart display; server-side Python/TA-Lib for signals shared with backtesting engine |
| Platform name | **Open** — QuantNexus / ArcLight Terminal / VectorEdge all approved; final choice at implementation start |

---

## Platform Name Proposals

| Option | Rationale |
|---|---|
| **QuantNexus** | Combines "quant" (quantitative finance) with "nexus" (central hub/connection point). Professional, memorable, domain-appropriate. |
| **ArcLight Terminal** | "Arc" evokes precision and trajectory; "Light" implies speed and clarity; "Terminal" directly signals Bloomberg-class tooling. |
| **VectorEdge** | "Vector" signals directional, mathematical trading; "Edge" signals the competitive advantage a quant platform provides. |

---

## Top-Level Overview

This plan covers the complete build of a Bloomberg Terminal / AlphaSpace-inspired trading dashboard — a dark-themed, data-dense, professional-grade front-end application with a decoupled Python data service back-end. The execution engine (C++ OMS, FIX protocol, live order routing) is explicitly out of scope for this planning phase and is documented for future phases only.

**What will be built:**
- A Next.js 15 (App Router) front-end dashboard with all core and advanced panels
- A FastAPI Python back-end data service providing REST and WebSocket endpoints
- A complete charting engine with all listed technical indicators and drawing tools
- A news sentiment scoring pipeline (NLP + AI API)
- A full data ingestion layer supporting all asset classes and multiple API providers
- Infrastructure (Docker, CI/CD, database schemas)

**What is explicitly deferred:**
- C++ execution engine and OMS
- FIX protocol integration
- Live order routing and brokerage connectivity
- Machine learning model training pipelines (signal generation models)
- Kubernetes production deployment

---

## Technology Stack — Final Decisions with Justifications

### Front-End

| Technology | Version | Justification |
|---|---|---|
| Next.js | 15 (App Router) | Server Components for initial load, streaming SSR, built-in API routes for BFF pattern if needed |
| React | 19 | Concurrent rendering for smooth real-time data updates without jank |
| TypeScript | 5.x | Required for a data-dense platform — type safety on all market data structures prevents silent bugs |
| TailwindCSS | 4.x | Utility-first, zero-runtime CSS — ideal for dense terminal UI with custom design tokens |
| Framer Motion | 11.x | Production-grade animation library; Apple-quality micro-animations for price ticks and transitions |
| TradingView Lightweight Charts | 4.x | Purpose-built for financial charting, 60fps canvas rendering, OHLCV native support, free and open source |
| D3.js | 7.x | Supplement TradingView for custom visualizations: heat maps, correlation matrix, volatility surface, yield curve |
| Zustand | 5.x | Minimal global state manager — simpler than Redux for real-time tick data; avoids unnecessary re-renders |
| TanStack Query | 5.x | Server state, caching, WebSocket integration, stale-while-revalidate for market data |
| TanStack Table | 8.x | Virtualized, sortable, filterable tables for positions, order history, screener |
| React Grid Layout | latest | Draggable, resizable widget grid for the Bloomberg-style multi-panel layout |
| Recharts | 2.x | Supplementary chart library for portfolio analytics, equity curves, P&L heatmaps |
| shadcn/ui | latest | Unstyled Radix UI primitives — provides accessible modals, dropdowns, tooltips customized to terminal theme |
| Lucide React | latest | Icon set consistent with terminal aesthetic |
| date-fns | 3.x | Date manipulation for time-series data formatting |
| numeral.js | latest | Financial number formatting (currency, compact notation, basis points) |

### Back-End Data Service

| Technology | Version | Justification |
|---|---|---|
| Python | 3.12 | Latest stable; asyncio improvements critical for high-concurrency WebSocket fan-out |
| FastAPI | 0.115.x | Async-native, WebSocket support built-in, automatic OpenAPI docs, fastest Python web framework |
| Uvicorn | 0.30.x | ASGI server; single-worker dev, multi-worker prod via Gunicorn |
| Pydantic | 2.x | Data validation and serialization for all market data models — V2 is 5–50x faster than V1 |
| SQLAlchemy | 2.x | Async ORM for PostgreSQL access |
| asyncpg | 0.29.x | Native async PostgreSQL driver — faster than psycopg2 for async workloads |
| redis-py | 5.x | Async Redis client for pub/sub and caching |
| httpx | 0.27.x | Async HTTP client for external API calls |
| websockets | 13.x | WebSocket client for upstream market data feeds |
| APScheduler | 3.x | Scheduled jobs for data refresh, feature computation |
| TA-Lib | 0.4.x | C-backed technical indicator library — ~50x faster than pure Python for indicator computation |
| pandas | 2.x | OHLCV data manipulation, resampling, rolling statistics |
| numpy | 1.x | Vectorized numerical computation |
| transformers | 4.x (HuggingFace) | FinBERT and general NLP models for sentiment scoring |
| spaCy | 3.x | Named entity recognition — extract ticker symbols from news text |
| openai | 1.x | OpenAI GPT-4o API for deep contextual news scoring |
| anthropic | 0.28.x | Anthropic Claude API as fallback/complement to OpenAI |
| celery | 5.x | Async task queue for sentiment scoring jobs (CPU-bound NLP offloaded from request path) |
| python-jose | 3.x | JWT token creation and validation |
| passlib | 1.x | Password hashing (bcrypt) |
| python-dotenv | 1.x | Environment variable management |
| structlog | 24.x | Structured JSON logging |

### Database Layer

| Technology | Use Case | Justification |
|---|---|---|
| TimescaleDB (PostgreSQL extension) | OHLCV bars, tick data, indicator snapshots | Time-series hypertables with automatic partitioning; SQL-compatible; continuous aggregates for OHLCV resampling |
| PostgreSQL 16 | Users, watchlists, alerts, strategy configs, fundamental data | Relational data with ACID guarantees |
| Redis 7.x | Real-time price cache, WebSocket pub/sub, session storage, rate limiting | Sub-millisecond reads; pub/sub for fan-out to connected dashboard clients |
| MongoDB 7.x | Alternative data: news articles, sentiment scores, earnings transcripts, SEC filings | Document model fits variable-structure news/filing data |

### Message Queue

| Technology | Use Case | Justification |
|---|---|---|
| Redis Streams | Intra-service event streaming for data pipeline | Lower operational overhead than Kafka for current scale; Redis already in stack; supports consumer groups |
| Apache Kafka | Documented as upgrade path when tick data volume exceeds Redis Streams capacity | Not required for Phase 1–4 |

### Infrastructure

| Technology | Use Case |
|---|---|
| Docker + Docker Compose | Local dev environment — all services containerized |
| GitHub Actions | CI/CD: lint, typecheck, test, build on every PR |
| NGINX | Reverse proxy, SSL termination, WebSocket upgrade, rate limiting |
| Prometheus + Grafana | Service metrics and alerting (Phase 7) |
| AWS (primary) or GCP | Cloud deployment target |

### Data APIs — All Options Documented

#### Equities (US Stocks & ETFs)

| Provider | Tier | Real-time? | Historical | Options? | Notes |
|---|---|---|---|---|---|
| **Alpaca Markets** | Free + Paid | Yes (WebSocket, IEX free / SIP paid) | 5+ years bars | No | Best free real-time option; paper trading ready |
| **Polygon.io** | Paid ($29/mo+) | Yes (WebSocket) | Full tick history | Yes | Best all-in-one equities + options + forex; recommended for production |
| **Alpha Vantage** | Free + Paid | No (polling, 5 req/min free) | 20+ years | No | Free tier only for prototyping |
| **Yahoo Finance (yfinance)** | Free (unofficial) | No (15min delay) | 20+ years | Yes (chain only) | Useful for historical backtesting data; not for production |
| **Tiingo** | Free + Paid | Yes (WebSocket, paid) | Full history | No | Good cost/quality ratio |
| **Twelve Data** | Free + Paid | Yes (WebSocket, paid) | Long history | No | Supports equities + forex + crypto |
| **NASDAQ Data Link (Quandl)** | Paid | No | Extensive | No | Best for fundamentals and alternative data |
| **FirstRate Data** | Paid (one-time) | No | Intraday tick | No | High-quality historical intraday data |

#### Options

| Provider | Tier | Real-time? | Greeks? | Notes |
|---|---|---|---|---|
| **Polygon.io** | Paid | Yes | Yes | Full options chain with Greeks, IV, OI |
| **Tradier** | Free + Paid | Yes (streaming) | Yes | Free tier includes options chain |
| **Unusual Whales** | Paid | Yes | Partial | Best for dark pool + unusual options activity feed |
| **CBOE DataShop** | Paid (institutional) | Yes | Yes | Institutional grade |

#### Crypto

| Provider | Tier | Real-time? | On-chain? | Notes |
|---|---|---|---|---|
| **Binance API** | Free | Yes (WebSocket) | No | Best liquidity data, global |
| **CoinGecko** | Free + Paid | No (polling) | Partial | Best for market cap, dominance, trending |
| **CoinMarketCap** | Free + Paid | No | No | Alternative to CoinGecko |
| **Glassnode** | Paid | No | Yes | Best on-chain metrics (funding rates, exchange flows, liquidation levels) |
| **Messari** | Free + Paid | No | Partial | Good for crypto fundamentals and research data |

#### Forex & Futures

| Provider | Tier | Real-time? | Notes |
|---|---|---|---|
| **Polygon.io** | Paid | Yes | Forex pairs WebSocket |
| **Twelve Data** | Free + Paid | Yes | Forex + commodities |
| **OANDA API** | Free (with account) | Yes | Forex; requires OANDA account |
| **Alpha Vantage** | Free | No | Forex polling |
| **Interactive Brokers API** | Requires IB account | Yes | Futures + forex; deferred to execution phase |

#### News & Alternative Data

| Provider | Use Case | Notes |
|---|---|---|
| **NewsAPI** | General news aggregation | Free tier: 100 req/day; paid for production |
| **Benzinga API** | Financial news with ticker tags | Paid; best structured financial news |
| **Seeking Alpha API** | Analyst articles and earnings | Paid |
| **Twitter/X API v2** | Social sentiment | Paid ($100/mo Basic tier for filtered streams) |
| **Reddit (Pushshift / PRAW)** | WSB, r/stocks sentiment | Free via PRAW |
| **SEC EDGAR** | 8-K, 10-K, earnings transcripts | Free public API |
| **FRED API** | Macro data (CPI, GDP, interest rates, yield curves) | Free, Federal Reserve |

---

## Complete Monorepo Folder and File Structure

```
/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml                   # Full local dev stack
├── docker-compose.override.yml          # Dev-only overrides (hot reload, debug ports)
├── Makefile                             # Convenience commands: make dev, make test, make build
│
├── frontend/                            # Next.js 15 App Router application
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── .eslintrc.json
│   ├── .prettierrc
│   ├── Dockerfile
│   │
│   ├── public/
│   │   ├── fonts/                       # JetBrains Mono, IBM Plex Mono, Inter
│   │   └── icons/                       # SVG asset class icons
│   │
│   ├── src/
│   │   ├── app/                         # Next.js App Router
│   │   │   ├── layout.tsx               # Root layout: theme provider, global styles
│   │   │   ├── page.tsx                 # Root redirect → /dashboard
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── layout.tsx
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx           # Dashboard shell: sidebar, header, ticker tape
│   │   │       ├── page.tsx             # Default dashboard — core panel grid
│   │   │       ├── charts/page.tsx      # Full-screen chart view
│   │   │       ├── screener/page.tsx    # Screener full page
│   │   │       ├── backtesting/page.tsx # Backtesting results page
│   │   │       └── settings/page.tsx    # User preferences, API keys, alerts
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── DashboardShell.tsx   # Top-level layout with resizable panel grid
│   │   │   │   ├── Sidebar.tsx          # Navigation sidebar
│   │   │   │   ├── Header.tsx           # Top header bar with search, user menu
│   │   │   │   ├── TickerTape.tsx       # Horizontally scrolling real-time price tape
│   │   │   │   └── PanelGrid.tsx        # React Grid Layout wrapper for draggable panels
│   │   │   │
│   │   │   ├── panels/                  # Each panel is a self-contained widget
│   │   │   │   ├── ChartPanel/
│   │   │   │   │   ├── index.tsx        # Panel wrapper with toolbar
│   │   │   │   │   ├── ChartCanvas.tsx  # TradingView Lightweight Charts mount
│   │   │   │   │   ├── ChartToolbar.tsx # Timeframe selector, chart type, indicator picker
│   │   │   │   │   ├── IndicatorOverlay.tsx
│   │   │   │   │   ├── DrawingTools.tsx
│   │   │   │   │   └── hooks/
│   │   │   │   │       ├── useChartData.ts
│   │   │   │   │       └── useIndicators.ts
│   │   │   │   │
│   │   │   │   ├── WatchlistPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── WatchlistRow.tsx
│   │   │   │   │   ├── WatchlistSearch.tsx
│   │   │   │   │   └── hooks/useWatchlist.ts
│   │   │   │   │
│   │   │   │   ├── PortfolioPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── EquitySummary.tsx       # Total equity, buying power, margin
│   │   │   │   │   ├── PnLDisplay.tsx          # Realized/unrealized P&L
│   │   │   │   │   ├── DrawdownMeter.tsx
│   │   │   │   │   └── PositionsTable.tsx
│   │   │   │   │
│   │   │   │   ├── NewsFeedPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── NewsItem.tsx            # Individual article with sentiment badge
│   │   │   │   │   ├── SentimentBadge.tsx      # Bullish/Bearish/Neutral + confidence %
│   │   │   │   │   ├── SentimentAggregator.tsx # Per-ticker aggregate sentiment score
│   │   │   │   │   └── hooks/useNewsFeed.ts
│   │   │   │   │
│   │   │   │   ├── OrderBookPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── BidAskLadder.tsx        # Level 2 depth visualization
│   │   │   │   │   └── DepthChart.tsx          # Cumulative depth chart
│   │   │   │   │
│   │   │   │   ├── TimeAndSalesPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   └── TapeRow.tsx             # Individual trade print
│   │   │   │   │
│   │   │   │   ├── OptionsChainPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── OptionsTable.tsx        # Calls/puts with Greeks
│   │   │   │   │   ├── ExpirySelector.tsx
│   │   │   │   │   └── IVRankBar.tsx
│   │   │   │   │
│   │   │   │   ├── HeatMapPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── SectorHeatMap.tsx       # D3.js treemap
│   │   │   │   │   └── hooks/useHeatMapData.ts
│   │   │   │   │
│   │   │   │   ├── CorrelationPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   └── CorrelationMatrix.tsx   # D3.js color matrix
│   │   │   │   │
│   │   │   │   ├── EconomicCalendarPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   └── EventRow.tsx
│   │   │   │   │
│   │   │   │   ├── ScreenerPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── FilterBuilder.tsx       # Chainable filter rules
│   │   │   │   │   └── ScreenerResultsTable.tsx
│   │   │   │   │
│   │   │   │   ├── AlertsPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   └── AlertRow.tsx
│   │   │   │   │
│   │   │   │   ├── RiskPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── VaRDisplay.tsx
│   │   │   │   │   ├── RatiosTable.tsx         # Sharpe, Sortino, Calmar, Beta, Alpha
│   │   │   │   │   └── PositionSizingCalc.tsx
│   │   │   │   │
│   │   │   │   ├── MacroPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── YieldCurveChart.tsx     # D3.js yield curve
│   │   │   │   │   └── MacroIndicatorGrid.tsx  # VIX, DXY, CPI, GDP tiles
│   │   │   │   │
│   │   │   │   ├── CryptoPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── FundingRateBar.tsx
│   │   │   │   │   ├── LiquidationHeatmap.tsx
│   │   │   │   │   └── OnChainMetrics.tsx
│   │   │   │   │
│   │   │   │   ├── BacktestPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── EquityCurveChart.tsx
│   │   │   │   │   ├── DrawdownChart.tsx
│   │   │   │   │   ├── MonthlyReturnsHeatmap.tsx
│   │   │   │   │   └── MetricsTable.tsx
│   │   │   │   │
│   │   │   │   ├── AIScorePanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── ConfidenceGauge.tsx
│   │   │   │   │   └── SentimentTimeline.tsx
│   │   │   │   │
│   │   │   │   ├── VolatilityPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── IVSurface.tsx           # 3D volatility surface (D3.js / Three.js)
│   │   │   │   │   └── IVRankHistory.tsx
│   │   │   │   │
│   │   │   │   ├── DarkPoolPanel/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   └── UnusualActivityTable.tsx
│   │   │   │   │
│   │   │   │   └── MTFPanel/
│   │   │   │       ├── index.tsx               # Multi-timeframe mini chart grid
│   │   │   │       └── MiniChart.tsx
│   │   │   │
│   │   │   ├── charts/                  # Chart primitives shared across panels
│   │   │   │   ├── indicators/          # Indicator compute + overlay components
│   │   │   │   │   ├── trend/
│   │   │   │   │   │   ├── MovingAverages.ts   # SMA, EMA, WMA, DEMA, TEMA, HMA, VWMA, ALMA, KAMA
│   │   │   │   │   │   ├── IchimokuCloud.ts
│   │   │   │   │   │   ├── ParabolicSAR.ts
│   │   │   │   │   │   ├── SuperTrend.ts
│   │   │   │   │   │   ├── LinearRegressionChannel.ts
│   │   │   │   │   │   ├── DonchianChannel.ts
│   │   │   │   │   │   └── KeltnerChannel.ts
│   │   │   │   │   ├── momentum/
│   │   │   │   │   │   ├── RSI.ts
│   │   │   │   │   │   ├── StochasticRSI.ts
│   │   │   │   │   │   ├── MACD.ts
│   │   │   │   │   │   ├── CCI.ts
│   │   │   │   │   │   ├── WilliamsR.ts
│   │   │   │   │   │   ├── ROC.ts
│   │   │   │   │   │   ├── UltimateOscillator.ts
│   │   │   │   │   │   ├── AwesomeOscillator.ts
│   │   │   │   │   │   └── TRIX.ts
│   │   │   │   │   ├── volatility/
│   │   │   │   │   │   ├── BollingerBands.ts
│   │   │   │   │   │   ├── ATR.ts
│   │   │   │   │   │   ├── HistoricalVolatility.ts
│   │   │   │   │   │   ├── ChaikinVolatility.ts
│   │   │   │   │   │   └── StdDevChannel.ts
│   │   │   │   │   ├── volume/
│   │   │   │   │   │   ├── VWAP.ts             # Daily, weekly, monthly, anchored
│   │   │   │   │   │   ├── OBV.ts
│   │   │   │   │   │   ├── VolumeProfile.ts    # VPVR, VPSV
│   │   │   │   │   │   ├── AccumulationDistribution.ts
│   │   │   │   │   │   ├── CMF.ts
│   │   │   │   │   │   ├── MFI.ts
│   │   │   │   │   │   ├── ForceIndex.ts
│   │   │   │   │   │   └── RVOL.ts
│   │   │   │   │   └── structure/
│   │   │   │   │       ├── SupportResistance.ts  # Auto-detection algorithm
│   │   │   │   │       ├── PivotPoints.ts        # Standard, Fib, Camarilla, Woodie, DeMark
│   │   │   │   │       ├── FibonacciLevels.ts
│   │   │   │   │       ├── ChartPatterns.ts      # H&S, double top/bottom, wedges, flags
│   │   │   │   │       ├── OrderBlocks.ts        # ICT order block detection
│   │   │   │   │       ├── FairValueGaps.ts
│   │   │   │   │       └── LiquidityLevels.ts
│   │   │   │   │
│   │   │   │   └── drawing/             # Drawing tool state and rendering
│   │   │   │       ├── DrawingManager.ts
│   │   │   │       ├── TrendLine.ts
│   │   │   │       ├── FibonacciTool.ts
│   │   │   │       ├── PitchforkTool.ts
│   │   │   │       ├── GannTool.ts
│   │   │   │       ├── ElliottWaveTool.ts
│   │   │   │       └── Annotation.ts
│   │   │   │
│   │   │   └── ui/                      # Shared shadcn/ui primitive overrides
│   │   │       ├── Button.tsx
│   │   │       ├── Badge.tsx
│   │   │       ├── Tooltip.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Dropdown.tsx
│   │   │       ├── Input.tsx
│   │   │       ├── Table.tsx
│   │   │       ├── Tabs.tsx
│   │   │       ├── Skeleton.tsx         # Loading state placeholders
│   │   │       └── Sparkline.tsx        # Micro-chart for watchlist rows
│   │   │
│   │   ├── hooks/                       # Global React hooks
│   │   │   ├── useWebSocket.ts          # Generic WebSocket hook with reconnect
│   │   │   ├── useMarketData.ts         # Subscribe to price stream for a symbol
│   │   │   ├── useTickerTape.ts         # Tape WebSocket subscription
│   │   │   ├── useNewsSentiment.ts      # News feed + sentiment polling
│   │   │   ├── usePortfolio.ts          # Portfolio state
│   │   │   ├── useAlerts.ts             # Alert CRUD + WebSocket trigger events
│   │   │   └── useTheme.ts             # Theme tokens
│   │   │
│   │   ├── store/                       # Zustand stores
│   │   │   ├── marketDataStore.ts       # Real-time quote map: symbol → quote
│   │   │   ├── watchlistStore.ts        # User watchlists (persisted)
│   │   │   ├── layoutStore.ts           # Panel grid layout config (persisted)
│   │   │   ├── chartStore.ts            # Active symbol, timeframe, indicators per panel
│   │   │   ├── portfolioStore.ts        # Positions, P&L, equity state
│   │   │   └── uiStore.ts              # Modal state, active panel focus
│   │   │
│   │   ├── lib/                         # Utilities and API client
│   │   │   ├── api/
│   │   │   │   ├── client.ts            # Base httpx-style fetch wrapper with auth headers
│   │   │   │   ├── market.ts            # Market data REST endpoints
│   │   │   │   ├── news.ts              # News and sentiment endpoints
│   │   │   │   ├── portfolio.ts         # Portfolio endpoints
│   │   │   │   ├── screener.ts          # Screener endpoints
│   │   │   │   └── websocket.ts         # WebSocket URL builders
│   │   │   ├── formatters.ts            # Price, volume, percent, currency formatters
│   │   │   ├── colors.ts                # Terminal color palette constants
│   │   │   ├── constants.ts             # Timeframes, asset classes, indicator defaults
│   │   │   └── indicators/              # Pure TypeScript indicator implementations
│   │   │       └── (mirrors charts/indicators/ but as pure compute functions, no rendering)
│   │   │
│   │   ├── types/                       # TypeScript type definitions
│   │   │   ├── market.ts                # Quote, OHLCV, Trade, OrderBook types
│   │   │   ├── portfolio.ts             # Position, Order, P&L types
│   │   │   ├── news.ts                  # NewsArticle, SentimentScore types
│   │   │   ├── options.ts               # OptionChain, Greeks, Strike types
│   │   │   ├── indicators.ts            # Indicator config and output types
│   │   │   └── api.ts                   # API response envelope types
│   │   │
│   │   └── styles/
│   │       ├── globals.css              # Tailwind base, CSS custom properties (design tokens)
│   │       └── terminal.css             # Bloomberg-specific overrides: scrollbars, selection colors
│   │
│   └── tests/
│       ├── unit/                        # Vitest unit tests for indicators and formatters
│       └── e2e/                         # Playwright end-to-end tests
│
├── backend/                             # FastAPI Python data service
│   ├── pyproject.toml                   # uv/pip project manifest
│   ├── requirements.txt                 # Locked dependencies
│   ├── Dockerfile
│   ├── alembic.ini                      # DB migration config
│   │
│   ├── app/
│   │   ├── main.py                      # FastAPI app factory, middleware registration
│   │   ├── config.py                    # Pydantic Settings — reads from environment
│   │   ├── dependencies.py              # FastAPI dependency injection (DB session, auth, cache)
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── router.py            # APIRouter aggregating all v1 routes
│   │   │   │   ├── market.py            # /market/quotes, /market/bars, /market/search
│   │   │   │   ├── news.py              # /news/feed, /news/sentiment/{ticker}
│   │   │   │   ├── portfolio.py         # /portfolio/positions, /portfolio/pnl
│   │   │   │   ├── watchlist.py         # /watchlist CRUD
│   │   │   │   ├── screener.py          # /screener/run
│   │   │   │   ├── options.py           # /options/chain/{ticker}
│   │   │   │   ├── calendar.py          # /calendar/events
│   │   │   │   ├── macro.py             # /macro/indicators (FRED data)
│   │   │   │   ├── crypto.py            # /crypto/onchain, /crypto/funding
│   │   │   │   ├── alerts.py            # /alerts CRUD + trigger evaluation
│   │   │   │   └── auth.py              # /auth/login, /auth/refresh, /auth/logout
│   │   │   │
│   │   │   └── ws/
│   │   │       ├── router.py            # WebSocket route registration
│   │   │       ├── market_feed.py       # WS /ws/market — real-time quotes fan-out
│   │   │       ├── tape_feed.py         # WS /ws/tape — time & sales stream
│   │   │       ├── orderbook_feed.py    # WS /ws/orderbook/{symbol} — Level 2
│   │   │       └── alerts_feed.py       # WS /ws/alerts — push triggered alerts
│   │   │
│   │   ├── services/
│   │   │   ├── market_data/
│   │   │   │   ├── base.py              # Abstract MarketDataProvider interface
│   │   │   │   ├── alpaca.py            # Alpaca Markets adapter
│   │   │   │   ├── polygon.py           # Polygon.io adapter
│   │   │   │   ├── alpha_vantage.py     # Alpha Vantage adapter
│   │   │   │   ├── yahoo_finance.py     # yfinance adapter (historical fallback)
│   │   │   │   ├── binance.py           # Binance adapter (crypto)
│   │   │   │   ├── coingecko.py         # CoinGecko adapter
│   │   │   │   ├── tiingo.py            # Tiingo adapter
│   │   │   │   ├── twelve_data.py       # Twelve Data adapter
│   │   │   │   └── router.py            # Provider selection logic (priority + fallback chain)
│   │   │   │
│   │   │   ├── news/
│   │   │   │   ├── aggregator.py        # Pulls from all news sources, deduplicates
│   │   │   │   ├── newsapi.py           # NewsAPI adapter
│   │   │   │   ├── benzinga.py          # Benzinga adapter
│   │   │   │   ├── reddit.py            # Reddit PRAW adapter (WSB, r/stocks)
│   │   │   │   ├── sec_edgar.py         # SEC EDGAR 8-K/10-K ingestion
│   │   │   │   └── twitter.py           # Twitter/X API v2 adapter
│   │   │   │
│   │   │   ├── sentiment/
│   │   │   │   ├── pipeline.py          # Orchestrates full scoring pipeline
│   │   │   │   ├── finbert.py           # FinBERT inference wrapper
│   │   │   │   ├── openai_scorer.py     # GPT-4o deep contextual scoring
│   │   │   │   ├── anthropic_scorer.py  # Claude scoring (fallback/complement)
│   │   │   │   ├── ner_extractor.py     # spaCy NER for ticker extraction
│   │   │   │   ├── aggregator.py        # Per-ticker weighted aggregate with time decay
│   │   │   │   └── models.py            # SentimentResult, AggregateScore Pydantic models
│   │   │   │
│   │   │   ├── indicators/
│   │   │   │   ├── engine.py            # Indicator computation orchestrator
│   │   │   │   ├── trend.py             # Server-side indicator compute (TA-Lib backed)
│   │   │   │   ├── momentum.py
│   │   │   │   ├── volatility.py
│   │   │   │   ├── volume.py
│   │   │   │   └── structure.py         # Support/resistance, pivot points
│   │   │   │
│   │   │   ├── screener/
│   │   │   │   ├── engine.py            # Filter evaluation engine
│   │   │   │   ├── fundamental.py       # P/E, P/B, EV/EBITDA filters
│   │   │   │   └── technical.py         # RSI range, MA cross, volume spike filters
│   │   │   │
│   │   │   ├── risk/
│   │   │   │   ├── var.py               # VaR and CVaR (historical, Monte Carlo, parametric)
│   │   │   │   ├── ratios.py            # Sharpe, Sortino, Calmar, Beta, Alpha
│   │   │   │   └── position_sizing.py   # Fixed fractional, Kelly Criterion
│   │   │   │
│   │   │   ├── options/
│   │   │   │   ├── chain.py             # Options chain fetching and Greeks computation
│   │   │   │   ├── greeks.py            # Black-Scholes Greeks implementation
│   │   │   │   └── iv_surface.py        # Volatility surface construction
│   │   │   │
│   │   │   ├── macro/
│   │   │   │   ├── fred.py              # FRED API client (rates, CPI, GDP)
│   │   │   │   └── yield_curve.py       # Yield curve construction and inversion detection
│   │   │   │
│   │   │   └── alerts/
│   │   │       ├── evaluator.py         # Evaluates alert conditions against live data
│   │   │       └── dispatcher.py        # Pushes triggered alerts via WebSocket + email/webhook
│   │   │
│   │   ├── data/
│   │   │   ├── ingestion/
│   │   │   │   ├── scheduler.py         # APScheduler jobs for periodic data refresh
│   │   │   │   ├── normalizer.py        # Normalize OHLCV across providers to canonical schema
│   │   │   │   └── writer.py            # Writes normalized data to TimescaleDB
│   │   │   │
│   │   │   └── cache/
│   │   │       ├── redis_client.py      # Redis connection pool and helpers
│   │   │       ├── quote_cache.py       # Read/write latest quotes from Redis
│   │   │       └── pubsub.py            # Redis pub/sub for WebSocket fan-out
│   │   │
│   │   ├── models/                      # SQLAlchemy ORM models
│   │   │   ├── ohlcv.py                 # TimescaleDB hypertable model
│   │   │   ├── tick.py                  # Tick data hypertable model
│   │   │   ├── user.py
│   │   │   ├── watchlist.py
│   │   │   ├── alert.py
│   │   │   ├── portfolio.py
│   │   │   ├── position.py
│   │   │   ├── news_article.py          # MongoDB-backed via Motor async driver
│   │   │   └── sentiment_score.py       # MongoDB-backed
│   │   │
│   │   ├── schemas/                     # Pydantic request/response schemas
│   │   │   ├── market.py
│   │   │   ├── news.py
│   │   │   ├── portfolio.py
│   │   │   ├── options.py
│   │   │   ├── screener.py
│   │   │   ├── alerts.py
│   │   │   └── auth.py
│   │   │
│   │   ├── auth/
│   │   │   ├── jwt.py                   # JWT creation, validation, refresh rotation
│   │   │   ├── totp.py                  # TOTP 2FA (pyotp)
│   │   │   └── rbac.py                  # Role-based access control decorators
│   │   │
│   │   └── tasks/                       # Celery async tasks
│   │       ├── celery_app.py            # Celery app factory
│   │       ├── sentiment_tasks.py       # Background NLP scoring jobs
│   │       ├── data_tasks.py            # Periodic OHLCV refresh jobs
│   │       └── alert_tasks.py           # Alert evaluation sweep
│   │
│   ├── migrations/                      # Alembic migrations
│   │   └── versions/
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
│
├── backtesting/                         # Python backtesting framework (deferred Phase 4)
│   ├── README.md
│   ├── pyproject.toml
│   ├── engine/
│   │   ├── vectorized.py                # NumPy/Pandas vectorized engine
│   │   ├── event_driven.py              # Event-driven simulation engine
│   │   └── simulator.py                # Fill simulation: slippage, partial fills, commissions
│   ├── strategies/                      # Example strategy implementations
│   ├── optimization/
│   │   ├── grid_search.py
│   │   ├── bayesian.py                  # Optuna-based Bayesian optimization
│   │   └── walk_forward.py
│   ├── reporting/
│   │   ├── metrics.py                   # All performance metrics computation
│   │   ├── html_report.py               # Jinja2 HTML report generator
│   │   └── pdf_report.py
│   └── tests/
│
├── ml/                                  # ML pipelines (deferred Phase 5)
│   ├── README.md
│   ├── pyproject.toml
│   ├── feature_store/
│   ├── models/
│   │   ├── lstm/
│   │   ├── transformer/
│   │   ├── xgboost/
│   │   └── hmm/                         # Hidden Markov Model for regime detection
│   ├── training/
│   ├── serving/                         # FastAPI model inference service
│   └── experiments/                     # MLflow experiment configs
│
├── engine/                              # C++ execution engine (deferred future phase)
│   ├── README.md
│   └── DEFERRED.md                      # Architecture notes for when this is built
│
├── infra/
│   ├── docker/
│   │   ├── frontend.Dockerfile
│   │   ├── backend.Dockerfile
│   │   └── nginx.conf
│   ├── k8s/                             # Kubernetes manifests (Phase 7)
│   │   └── README.md
│   ├── terraform/                       # AWS/GCP IaC (Phase 7)
│   │   └── README.md
│   └── monitoring/
│       ├── prometheus.yml
│       └── grafana/
│           └── dashboards/
│
├── docs/
│   ├── architecture/
│   │   ├── system-overview.md
│   │   ├── data-flow.md
│   │   ├── api-contract.md
│   │   └── database-schema.md
│   ├── developer/
│   │   ├── local-setup.md
│   │   ├── adding-indicators.md
│   │   └── adding-data-providers.md
│   └── decisions/                       # Architecture Decision Records (ADRs)
│       ├── ADR-001-frontend-framework.md
│       ├── ADR-002-database-selection.md
│       └── ADR-003-websocket-architecture.md
│
└── tests/
    ├── e2e/                             # Playwright cross-service E2E tests
    └── load/                            # k6 load tests for WebSocket fan-out
```

---

## Database Schema

### TimescaleDB — OHLCV Hypertable

```sql
-- Canonical OHLCV bars across all asset classes
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

-- Continuous aggregate for daily bars from minute data
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

```sql
-- Tick data (trade prints)
CREATE TABLE ticks (
    time        TIMESTAMPTZ     NOT NULL,
    symbol      TEXT            NOT NULL,
    price       NUMERIC(20, 8)  NOT NULL,
    size        NUMERIC(20, 8)  NOT NULL,
    side        CHAR(1),                   -- B=buy, S=sell, U=unknown
    exchange    TEXT,
    conditions  TEXT[],
    provider    TEXT            NOT NULL
);

SELECT create_hypertable('ticks', 'time', chunk_time_interval => INTERVAL '1 hour');
CREATE INDEX ON ticks (symbol, time DESC);
```

```sql
-- Level 2 / Order Book snapshots
CREATE TABLE order_book_snapshots (
    time        TIMESTAMPTZ     NOT NULL,
    symbol      TEXT            NOT NULL,
    bids        JSONB           NOT NULL,  -- [[price, size], ...]
    asks        JSONB           NOT NULL,
    provider    TEXT            NOT NULL
);

SELECT create_hypertable('order_book_snapshots', 'time', chunk_time_interval => INTERVAL '1 hour');
```

### PostgreSQL — Relational Tables

```sql
-- Users
CREATE TABLE users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT            UNIQUE NOT NULL,
    password_hash   TEXT            NOT NULL,
    totp_secret     TEXT,                        -- Encrypted at rest
    role            TEXT            NOT NULL DEFAULT 'trader',  -- admin, trader, analyst, readonly
    is_active       BOOLEAN         NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Watchlists
CREATE TABLE watchlists (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    symbols     TEXT[]      NOT NULL DEFAULT '{}',
    is_default  BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Alerts
CREATE TABLE alerts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol          TEXT        NOT NULL,
    alert_type      TEXT        NOT NULL,   -- price, indicator, news_keyword, pnl
    condition       JSONB       NOT NULL,   -- {"field": "price", "op": "gte", "value": 150.00}
    message         TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT true,
    triggered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dashboard layout configurations
CREATE TABLE dashboard_layouts (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    layout      JSONB       NOT NULL,   -- React Grid Layout serialized config
    is_default  BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Portfolio snapshots (paper trading / imported)
CREATE TABLE portfolios (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT            NOT NULL,
    initial_capital NUMERIC(20, 2)  NOT NULL,
    currency        TEXT            NOT NULL DEFAULT 'USD',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Positions
CREATE TABLE positions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID            NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol          TEXT            NOT NULL,
    asset_class     TEXT            NOT NULL,
    side            TEXT            NOT NULL,   -- long, short
    quantity        NUMERIC(20, 8)  NOT NULL,
    avg_entry_price NUMERIC(20, 8)  NOT NULL,
    stop_loss       NUMERIC(20, 8),
    take_profit     NUMERIC(20, 8),
    opened_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    is_open         BOOLEAN         NOT NULL DEFAULT true
);

-- Fundamental data (refreshed daily)
CREATE TABLE fundamentals (
    symbol          TEXT        NOT NULL,
    as_of_date      DATE        NOT NULL,
    market_cap      NUMERIC,
    pe_ratio        NUMERIC,
    pb_ratio        NUMERIC,
    ev_ebitda       NUMERIC,
    revenue_ttm     NUMERIC,
    net_income_ttm  NUMERIC,
    gross_margin    NUMERIC,
    debt_equity     NUMERIC,
    dividend_yield  NUMERIC,
    beta            NUMERIC,
    sector          TEXT,
    industry        TEXT,
    PRIMARY KEY (symbol, as_of_date)
);

-- Economic calendar events
CREATE TABLE economic_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time      TIMESTAMPTZ NOT NULL,
    country         TEXT        NOT NULL,
    event_name      TEXT        NOT NULL,
    impact          TEXT        NOT NULL,   -- high, medium, low
    forecast        TEXT,
    previous        TEXT,
    actual          TEXT,
    currency        TEXT
);

-- Audit log
CREATE TABLE audit_log (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        REFERENCES users(id),
    action      TEXT        NOT NULL,
    resource    TEXT        NOT NULL,
    details     JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Redis Key Structures

```
# Latest quote per symbol (Hash)
quote:{symbol}              → {price, bid, ask, volume, change_pct, timestamp}
quote:{symbol}:options      → {iv_rank, put_call_ratio, timestamp}

# Pub/Sub channels
channel:quotes              → broadcast all quote updates (JSON payload)
channel:quotes:{symbol}     → per-symbol quote updates
channel:tape                → all time & sales prints
channel:tape:{symbol}       → per-symbol tape
channel:orderbook:{symbol}  → Level 2 updates
channel:alerts:{user_id}    → per-user triggered alerts

# Rate limiting (String with TTL)
ratelimit:{user_id}:{endpoint}  → request count

# Session tokens (String with TTL)
session:{token_jti}         → {user_id, role, expires_at}

# Sentiment cache (String with TTL = 5 minutes)
sentiment:{symbol}          → {score, confidence, article_count, updated_at}

# Screener result cache (String with TTL = 60 seconds)
screener:{hash_of_filters}  → [list of matching symbols with scores]

# OHLCV latest bar cache (Hash)
bar:{symbol}:{timeframe}:latest → {open, high, low, close, volume, time}
```

### MongoDB Collections

```javascript
// news_articles collection
{
  _id: ObjectId,
  source: "benzinga" | "newsapi" | "seeking_alpha" | "reddit" | "sec_edgar" | "twitter",
  source_id: String,          // original article ID from provider
  headline: String,
  body: String,               // full article text (if available)
  url: String,
  published_at: ISODate,
  tickers_mentioned: [String], // extracted by spaCy NER
  sentiment: {
    finbert_score: Number,    // -1 to +1
    finbert_confidence: Number,
    openai_score: Number,
    openai_confidence: Number,
    composite_score: Number,  // weighted average
    label: "bullish" | "bearish" | "neutral",
    impact_category: "earnings" | "macro" | "regulatory" | "ma" | "analyst" | "general"
  },
  processed_at: ISODate
}

// ticker_sentiment_aggregate collection (updated on each new article)
{
  _id: ObjectId,
  symbol: String,
  updated_at: ISODate,
  score_1h: Number,           // time-decay weighted composite, last 1 hour
  score_4h: Number,
  score_1d: Number,
  article_count_1h: Number,
  article_count_1d: Number,
  dominant_label: "bullish" | "bearish" | "neutral",
  top_articles: [ObjectId]    // references to top 3 most impactful recent articles
}
```

---

## Full API Contract

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Login with email + password; returns access + refresh tokens |
| POST | `/api/v1/auth/refresh` | Exchange refresh token for new access token |
| POST | `/api/v1/auth/logout` | Invalidate session |
| POST | `/api/v1/auth/totp/setup` | Initiate TOTP 2FA setup — returns QR code |
| POST | `/api/v1/auth/totp/verify` | Verify TOTP code to complete 2FA setup |

### Market Data

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/market/quotes` | Batch latest quotes: `?symbols=AAPL,MSFT,BTC-USD` |
| GET | `/api/v1/market/bars/{symbol}` | OHLCV bars: `?timeframe=1h&start=ISO&end=ISO&limit=500` |
| GET | `/api/v1/market/search` | Symbol search: `?q=apple&asset_class=equity` |
| GET | `/api/v1/market/snapshot/{symbol}` | Full snapshot: quote + fundamentals + sentiment summary |
| GET | `/api/v1/market/tape/{symbol}` | Recent time & sales: `?limit=100` |
| GET | `/api/v1/market/orderbook/{symbol}` | Current order book: `?depth=20` |

### Options

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/options/chain/{symbol}` | Full options chain: `?expiry=2025-01-17` |
| GET | `/api/v1/options/expirations/{symbol}` | Available expiration dates |
| GET | `/api/v1/options/iv-surface/{symbol}` | Volatility surface data |
| GET | `/api/v1/options/unusual-activity` | Unusual options flow: `?symbol=AAPL&min_premium=100000` |

### News & Sentiment

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/news/feed` | Paginated news feed: `?symbols=AAPL&limit=50&page=1` |
| GET | `/api/v1/news/sentiment/{symbol}` | Aggregate sentiment score for a symbol |
| GET | `/api/v1/news/sentiment/batch` | Batch sentiment: `?symbols=AAPL,MSFT` |

### Screener

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/screener/run` | Run screener with filter payload (see schema below) |
| GET | `/api/v1/screener/presets` | Saved screener presets |
| POST | `/api/v1/screener/presets` | Save a screener preset |

### Watchlist

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/watchlist` | All user watchlists |
| POST | `/api/v1/watchlist` | Create watchlist |
| PUT | `/api/v1/watchlist/{id}` | Update (rename, add/remove symbols) |
| DELETE | `/api/v1/watchlist/{id}` | Delete watchlist |

### Alerts

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/alerts` | All user alerts |
| POST | `/api/v1/alerts` | Create alert |
| PUT | `/api/v1/alerts/{id}` | Update alert |
| DELETE | `/api/v1/alerts/{id}` | Delete alert |

### Portfolio

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/portfolio` | Portfolio summary (equity, P&L, margin) |
| GET | `/api/v1/portfolio/positions` | Open positions |
| GET | `/api/v1/portfolio/history` | Closed positions / trade history |
| GET | `/api/v1/portfolio/risk` | VaR, CVaR, Sharpe, Sortino, Beta, Alpha, drawdown |

### Macro

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/macro/indicators` | VIX, DXY, MOVE index, Fed funds rate |
| GET | `/api/v1/macro/yield-curve` | US Treasury yield curve data |
| GET | `/api/v1/macro/fred/{series_id}` | Arbitrary FRED series |
| GET | `/api/v1/calendar/events` | Economic calendar: `?start=ISO&end=ISO&impact=high` |

### Crypto

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/crypto/funding-rates` | Perpetual funding rates: `?symbols=BTC,ETH` |
| GET | `/api/v1/crypto/onchain/{symbol}` | On-chain metrics (Glassnode) |
| GET | `/api/v1/crypto/liquidations` | Liquidation level heatmap data |
| GET | `/api/v1/crypto/exchange-flows` | Exchange inflow/outflow |

### WebSocket Events

All WebSocket connections require a JWT token passed as a query parameter: `?token=<access_token>`

```
WS /ws/market
  Subscribe: { "action": "subscribe", "symbols": ["AAPL", "BTC-USD", "EUR-USD"] }
  Unsubscribe: { "action": "unsubscribe", "symbols": ["AAPL"] }
  Server → Client (Quote Update):
    {
      "type": "quote",
      "symbol": "AAPL",
      "price": 198.45,
      "bid": 198.44,
      "ask": 198.46,
      "bid_size": 200,
      "ask_size": 150,
      "volume": 42_500_000,
      "change": 1.23,
      "change_pct": 0.624,
      "timestamp": "2025-01-15T14:32:01.123Z"
    }

WS /ws/tape
  Subscribe: { "action": "subscribe", "symbols": ["AAPL"] }
  Server → Client (Trade Print):
    {
      "type": "trade",
      "symbol": "AAPL",
      "price": 198.45,
      "size": 500,
      "side": "B",
      "exchange": "NASDAQ",
      "timestamp": "2025-01-15T14:32:01.089Z"
    }

WS /ws/orderbook/{symbol}
  Server → Client (Order Book Update):
    {
      "type": "orderbook",
      "symbol": "AAPL",
      "bids": [[198.44, 200], [198.43, 500], ...],
      "asks": [[198.46, 150], [198.47, 300], ...],
      "timestamp": "2025-01-15T14:32:01.105Z"
    }

WS /ws/alerts
  Server → Client (Alert Triggered):
    {
      "type": "alert_triggered",
      "alert_id": "uuid",
      "symbol": "AAPL",
      "message": "AAPL crossed above $200",
      "timestamp": "2025-01-15T14:32:01.200Z"
    }
```

### Screener Request Schema

```json
{
  "asset_class": "equity",
  "filters": [
    { "field": "market_cap", "op": "gte", "value": 1000000000 },
    { "field": "pe_ratio", "op": "lte", "value": 25 },
    { "field": "rsi_14", "op": "lte", "value": 35 },
    { "field": "volume_ratio", "op": "gte", "value": 2.0 },
    { "field": "sector", "op": "in", "value": ["Technology", "Healthcare"] }
  ],
  "sort_by": "market_cap",
  "sort_dir": "desc",
  "limit": 100
}
```

---

## Architecture Diagrams (ASCII/Text)

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT BROWSER                                │
│                        Next.js 15 Dashboard                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│   │  Chart Panel │  │ Watchlist    │  │ News/Sentiment│  ... (25+ panels)│
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
│          │  REST/WS        │  REST/WS          │  REST                  │
└──────────┼─────────────────┼───────────────────┼────────────────────────┘
           │                 │                   │
           ▼                 ▼                   ▼
┌──────────────────────────────────────────────────────────┐
│                      NGINX Reverse Proxy                  │
│          SSL Termination · Rate Limiting · WS Upgrade     │
└──────────────────────────┬───────────────────────────────┘
                           │
           ┌───────────────┼──────────────────────┐
           ▼               ▼                      ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  FastAPI     │  │  FastAPI         │  │  Celery Worker   │
│  REST API    │  │  WebSocket Layer │  │  (NLP/Sentiment) │
│  (Uvicorn)   │  │  (Uvicorn)       │  │  (Redis broker)  │
└──────┬───────┘  └──────┬───────────┘  └──────┬───────────┘
       │                 │                      │
       ▼                 ▼                      │
┌─────────────────────────────────┐             │
│         Redis 7                 │ ◄───────────┘
│  Pub/Sub · Cache · Sessions     │
└────────────────┬────────────────┘
                 │
    ┌────────────┼─────────────────────────────────┐
    ▼            ▼                                 ▼
┌──────────┐ ┌──────────────┐            ┌──────────────────┐
│TimescaleDB│ │ PostgreSQL   │            │    MongoDB       │
│OHLCV/Tick │ │ Users/Config │            │ News/Sentiment   │
└──────────┘ └──────────────┘            └──────────────────┘

    ▲
    │  Data Ingestion Services (async background tasks)
    │
┌───┴────────────────────────────────────────────────────────┐
│                    External Data APIs                       │
│  Alpaca · Polygon · Binance · CoinGecko · Twelve Data      │
│  NewsAPI · Benzinga · Reddit · SEC EDGAR · FRED · Twitter  │
└────────────────────────────────────────────────────────────┘
```

### Data Flow

```
External API WebSocket
        │
        ▼
  [Ingestion Service]          # Python async websocket client
        │
        ├──► Normalize OHLCV   # Canonical schema conversion
        │         │
        │         ├──► TimescaleDB (persist bars)
        │         └──► Redis PUBLISH channel:quotes:{symbol}
        │
        └──► Redis PUBLISH channel:tape (tick data)

Redis SUBSCRIBE
        │
        ▼
  [FastAPI WS Handler]         # One handler per connected client
        │
        ▼
  [Client WebSocket]           # Browser receives JSON quote updates
```

### Sentiment Scoring Pipeline

```
News Sources (polling/WebSocket)
        │
        ▼
  [News Aggregator Service]    # Deduplication, normalization
        │
        ▼
  [Celery Task Queue]          # Async scoring jobs
        │
        ├──► [spaCy NER]       # Extract ticker symbols from text
        │
        ├──► [FinBERT]         # Fast local inference: sentiment score
        │
        └──► [OpenAI GPT-4o]   # Deep contextual scoring (sampled for cost control)
                │
                ▼
        [Aggregator]           # Time-decay weighted composite per ticker
                │
                ├──► MongoDB (persist article + scores)
                └──► Redis SET sentiment:{symbol} (cache 5 min)
                          │
                          ▼
                [FastAPI /news/sentiment/{symbol}]
                          │
                          ▼
                    [Dashboard AI Panel]
```

---

## Enterprise-Level Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **API rate limits** — Free-tier providers throttle aggressively | High | Implement multi-provider fallback chain in `services/market_data/router.py`; cache aggressively in Redis; use paid tiers for production |
| **WebSocket fan-out memory pressure** — Thousands of subscriptions per server | High | Use Redis pub/sub as the single source of truth; FastAPI WS handlers are thin subscribers only; horizontal scaling behind NGINX upstream |
| **FinBERT / LLM inference latency** — NLP scoring blocks news feed freshness | High | All NLP scoring runs in Celery workers asynchronously; dashboard reads pre-scored results from Redis/MongoDB cache; never blocks the request path |
| **TimescaleDB chunk size tuning** — Poor chunk intervals destroy query performance | Medium | Use 1-day chunks for 1m bars, 1-week for daily bars; set up continuous aggregates for OHLCV resampling from day one |
| **JWT secret rotation** — Stale tokens after secret rotation lock out users | Medium | Use short-lived access tokens (15 min) + long-lived refresh tokens (7 days) with Redis-backed token family rotation |
| **Provider data inconsistency** — Different providers return slightly different OHLCV values | Medium | Normalizer layer records `provider` field on every bar; implement conflict resolution rules (prefer paid providers) |
| **OpenAI/Anthropic API costs** — Scoring every article through GPT-4o is expensive | Medium | Use FinBERT as the primary scorer for all articles; invoke GPT-4o only for high-impact articles (earnings calls, Fed statements, M&A) via impact classification gate |
| **Front-end re-render storms** — 25+ panels all subscribing to the same WebSocket | Medium | Zustand `marketDataStore` receives one WebSocket; panels select only their symbol's slice; use `useMemo` and selector granularity to prevent cascading re-renders |
| **CORS misconfiguration** — Wide-open CORS in dev bleeds to production | Low-Medium | Enforce strict `ALLOWED_ORIGINS` in FastAPI config loaded from environment; NGINX enforces independently |
| **Secrets in environment** — API keys for 10+ providers are sensitive | High | All secrets via environment variables only; `.env` in `.gitignore`; AES-256 encryption of stored API keys in DB; document rotation procedure |
| **Technical indicator numerical drift** — Floating-point precision in rolling computations | Low | Use `numpy float64` throughout; document precision limitations in `adding-indicators.md` developer guide |
| **Browser memory growth** — Infinite tick accumulation in `marketDataStore` | Medium | Implement sliding window in store (keep last N ticks per symbol, configurable); clean up subscriptions on component unmount |

---

## Regulatory and Licensing Requirements

The following must be resolved before any live data or trading functionality is enabled:

| Requirement | Details |
|---|---|
| **Polygon.io redistribution terms** | Polygon free tier data cannot be redistributed. If this platform is ever multi-user, a commercial data license is required. |
| **Alpaca Markets account** | Requires a US-based account for SIP real-time data. Non-US residents receive IEX feed only (subset of trades). |
| **Binance API geographic restrictions** | Binance.com is restricted in the US. US users must use Binance.US API (`api.binance.us`), which has a reduced asset list. |
| **Twitter/X API** | Paid Basic tier ($100/mo) required for any filtered stream access. Free tier allows only 1 app-level stream. |
| **OpenAI API usage policy** | Financial advice or trade recommendations based on OpenAI output must comply with OpenAI's usage policies. The platform must display clear disclaimers that AI scores are not investment advice. |
| **FINRA / SEC compliance (if live trading added)** | Once live order execution is added, SEC Rule 15c3-5 (Market Access Rule) mandates pre-trade risk checks, which are already designed into the deferred OMS architecture. |
| **Display of real-time data** | Most real-time data vendors require end-user license agreements. If this platform serves multiple users, each provider's redistribution policy must be reviewed and appropriate licenses obtained. |

---

## Compute Infrastructure Requirements

### Local Development (Single Developer)
- Docker Compose runs all services on a single machine
- Minimum recommended: 16 GB RAM, 8-core CPU, 50 GB SSD free
- GPU optional but beneficial for local FinBERT inference (CUDA-capable)

### Cloud Deployment (Single-User Production / Phase 7)

| Service | AWS Equivalent | Spec | Est. Monthly Cost |
|---|---|---|---|
| Next.js frontend | Vercel or EC2 t3.small | 2 vCPU, 2 GB RAM | $0–$20 (Vercel free tier or EC2) |
| FastAPI backend | EC2 t3.medium | 2 vCPU, 4 GB RAM | ~$35 |
| Celery workers (NLP) | EC2 c6i.large | 2 vCPU, 4 GB RAM, 2× for redundancy | ~$140 |
| TimescaleDB | RDS db.t3.medium | 2 vCPU, 4 GB RAM, 100 GB gp3 | ~$65 |
| PostgreSQL | Shared with TimescaleDB | — | $0 (same instance) |
| Redis | ElastiCache cache.t3.micro | 0.5 GB | ~$15 |
| MongoDB | Atlas M10 | 2 vCPU, 2 GB RAM, 10 GB | ~$57 |
| NGINX | Included in EC2 | — | $0 |
| Data transfer & misc | — | — | ~$20 |
| **Total** | | | **~$332–$352/month** |

### Scale-Up Path (Multi-User / Phase 7+)

Add: Application Load Balancer (~$20), Auto Scaling Group for FastAPI, Redis Cluster mode, TimescaleDB read replicas, Kafka for tick data fan-out. Estimated cost jumps to ~$800–$1,500/month depending on concurrent user count.

---

## Phased Implementation Roadmap

### Phase 1 — Foundation
**Goal:** Running monorepo with authentication, database schemas, and a dark-themed dashboard skeleton.

**Sub-tasks:**
1. Monorepo scaffold: Next.js 15 + FastAPI + Docker Compose + GitHub Actions CI
2. Database initialization: TimescaleDB hypertables, PostgreSQL schema, Redis config, MongoDB setup
3. Authentication system: JWT + refresh rotation + TOTP 2FA (backend) + login page (frontend)
4. Design system: TailwindCSS tokens for terminal theme (black, greens, blues, ambers), JetBrains Mono typography, shadcn/ui primitive overrides
5. Dashboard shell: Sidebar + Header + React Grid Layout empty panel grid with drag/resize

### Phase 2 — Data Layer & Core Charting
**Goal:** Real-time price data flowing to the three highest-priority panels: Chart, Watchlist, Ticker Tape.

**Sub-tasks:**
1. Market data provider abstraction layer + at least two adapters (Alpaca + yfinance fallback)
2. OHLCV ingestion pipeline → TimescaleDB → Redis pub/sub
3. FastAPI REST endpoints: `/market/bars`, `/market/quotes`, `/market/search`
4. FastAPI WebSocket: `/ws/market` with Redis pub/sub fan-out
5. TradingView Lightweight Charts integration: candlestick, all timeframes, ChartToolbar
6. All trend + momentum + volatility + volume indicator implementations (TypeScript client-side + TA-Lib server-side)
7. Watchlist panel with real-time quotes via WebSocket
8. Ticker tape component with WebSocket subscription

### Phase 3 — News, Sentiment & AI Scoring
**Goal:** Live news feed with per-article AI sentiment scores and per-ticker aggregate sentiment.

**Sub-tasks:**
1. News aggregator: NewsAPI + Benzinga adapters
2. FinBERT inference service (local model, CPU inference)
3. spaCy NER ticker extraction pipeline
4. Celery task queue: async scoring pipeline
5. OpenAI GPT-4o deep scoring (gated to high-impact articles)
6. MongoDB news + sentiment storage
7. `/news/feed` and `/news/sentiment/{symbol}` REST endpoints
8. NewsFeedPanel: article list with SentimentBadge, confidence %, impact category
9. AIScorePanel: per-ticker aggregate score with timeline

### Phase 4 — Portfolio, Risk & Secondary Panels
**Goal:** Portfolio overview, positions, risk metrics, and all secondary visualization panels.

**Sub-tasks:**
1. Portfolio and position data models + REST endpoints
2. PortfolioPanel: equity, P&L, drawdown meter
3. Risk calculations: VaR, CVaR, Sharpe, Sortino, Calmar, Beta, Alpha (backend)
4. RiskPanel UI
5. OptionsChainPanel: chain data from Polygon or Tradier, Black-Scholes Greeks
6. OrderBookPanel (Level 2) + TimeAndSalesPanel via `/ws/tape` and `/ws/orderbook`
7. HeatMapPanel: D3.js treemap for sector heat maps
8. CorrelationMatrix: D3.js color matrix
9. EconomicCalendarPanel: FRED + external calendar source
10. MacroPanel: VIX, DXY, yield curve
11. ScreenerPanel: filter builder + results table

### Phase 5 — Advanced Panels & Crypto
**Goal:** All remaining panels from the spec, crypto asset class, dark pool feed.

**Sub-tasks:**
1. CryptoPanel: Binance funding rates, CoinGecko data, on-chain metrics
2. VolatilityPanel: IV surface (D3.js / Three.js 3D surface)
3. DarkPoolPanel: Unusual Whales adapter or Polygon dark pool endpoint
4. MTFPanel: multi-timeframe mini chart grid
5. AlertsPanel: CRUD + WebSocket push via `/ws/alerts`
6. Advanced charting: all drawing tools (Fibonacci, Pitchfork, Gann, Elliott Wave, annotations)
7. All remaining chart types: Heikin-Ashi, Renko, Line Break, P&F, Kagi
8. BacktestPanel: equity curve, drawdown, monthly heatmap (connects to backtesting service)
9. StrategyBuilder UI skeleton (drag-and-drop logic blocks)

### Phase 6 — Backtesting Framework (deferred module)
**Goal:** Fully functional vectorized and event-driven backtesting engine, performance reporting.

**Sub-tasks:**
1. Vectorized backtesting engine (NumPy/Pandas)
2. Event-driven engine
3. Commission + slippage + partial fill simulation
4. Walk-forward optimization + Optuna Bayesian search
5. HTML/PDF report generation
6. BacktestPanel wired to live backtesting service

### Phase 7 — Hardening & Enterprise Readiness
**Goal:** Security audit, performance optimization, monitoring, cloud deployment.

**Sub-tasks:**
1. Security audit: dependency scanning (Mend/Snyk), SAST (Bandit for Python, ESLint security plugin)
2. Prometheus metrics instrumentation (FastAPI + Celery)
3. Grafana dashboards for service health
4. Load testing: k6 WebSocket fan-out benchmark (target: 1,000 concurrent subscribers)
5. FastAPI async profiling: identify and fix blocking I/O in hot paths
6. TimescaleDB query optimization: EXPLAIN ANALYZE on all critical queries, index review
7. Compliance logging: audit_log table wired to all auth and data access events
8. AWS deployment: Terraform IaC for full stack, HTTPS via ACM, Route 53
9. Full documentation: API docs (auto-generated by FastAPI), architecture diagrams, developer onboarding guide

---

## Sub-Tasks for Plan Execution

Each sub-task below maps to a self-contained implementation unit.

---

### Sub-Task 1 — Monorepo Scaffold and CI/CD
**Intent:** Establish the full project skeleton so every subsequent sub-task has a correct, working foundation to build on.
**Expected Outcomes:**
- `frontend/` initialized as a Next.js 15 App Router TypeScript project with TailwindCSS 4
- `backend/` initialized as a FastAPI Python project with `pyproject.toml` and `uv`
- `docker-compose.yml` starts TimescaleDB, PostgreSQL, Redis, MongoDB, frontend, backend, Celery worker
- GitHub Actions CI runs lint + typecheck + tests on every PR
- `.gitignore` covers all secrets, build artifacts, and virtual environments
- `.env.example` documents every required environment variable

**Todo List:**
1. Create `frontend/` with `npx create-next-app@latest` (TypeScript, App Router, TailwindCSS, ESLint)
2. Install frontend dependencies: Framer Motion, Zustand, TanStack Query, TanStack Table, React Grid Layout, shadcn/ui, Lucide React, TradingView Lightweight Charts, D3.js, Recharts, date-fns, numeral
3. Configure `tailwind.config.ts` with terminal design tokens (color palette, fonts)
4. Create `backend/` with `uv init`, configure `pyproject.toml` with all dependencies
5. Create `docker-compose.yml` with all service definitions
6. Create `backend/app/main.py` FastAPI app factory with CORS middleware
7. Create `.github/workflows/ci.yml` with lint, typecheck, test jobs
8. Create `.env.example` with all required variable names (no values)
9. Create `Makefile` with `make dev`, `make test`, `make lint`, `make build` targets
10. Verify `make dev` starts all services cleanly

**Relevant Context:** Blank slate project — no existing code. All technology choices are documented in the Technology Stack section above.
**Status:** `[ ] pending`

---

### Sub-Task 2 — Database Schema Initialization
**Intent:** Create all database schemas, TimescaleDB hypertables, and Redis key conventions so all subsequent services have a stable data layer.
**Expected Outcomes:**
- Alembic migrations create all PostgreSQL tables
- TimescaleDB hypertables for `ohlcv` and `ticks` with correct chunk intervals and indexes
- Continuous aggregate view `ohlcv_daily` defined
- MongoDB indexes on `news_articles.tickers_mentioned`, `news_articles.published_at`
- Redis key conventions documented in `docs/architecture/database-schema.md`

**Todo List:**
1. Write SQLAlchemy ORM models for all PostgreSQL tables
2. Generate initial Alembic migration
3. Write TimescaleDB hypertable creation SQL (executed post-migration)
4. Write MongoDB index creation script
5. Write `backend/app/data/cache/redis_client.py` with connection pool
6. Write database schema documentation

**Relevant Context:** Full schema is defined in the Database Schema section above.
**Status:** `[ ] pending`

---

### Sub-Task 3 — Authentication System
**Intent:** Implement JWT + refresh token rotation + TOTP 2FA so the dashboard is secured from the first deployed commit.
**Expected Outcomes:**
- `POST /api/v1/auth/login` returns access token (15 min TTL) + refresh token (7 day TTL)
- Refresh token rotation: each refresh invalidates the old token family in Redis
- `POST /api/v1/auth/totp/setup` and `/verify` enable 2FA
- RBAC decorator enforces `admin`, `trader`, `analyst`, `readonly` roles on protected endpoints
- Login page in Next.js with form validation and error states

**Todo List:**
1. Implement `backend/app/auth/jwt.py`
2. Implement `backend/app/auth/totp.py` using `pyotp`
3. Implement `backend/app/auth/rbac.py`
4. Implement `backend/app/api/v1/auth.py` routes
5. Write unit tests for token creation, validation, rotation, and expiry
6. Build `frontend/src/app/(auth)/login/page.tsx`
7. Build `frontend/src/lib/api/client.ts` with Authorization header injection and 401 refresh logic

**Relevant Context:** JWT secret and all credentials must come from environment variables per security rules. NEVER hardcode. Use `secrets.token_urlsafe()` for refresh token generation.
**Status:** `[ ] pending`

---

### Sub-Task 4 — Design System and Dashboard Shell
**Intent:** Build the full visual shell — dark terminal theme, typography, layout skeleton — so all subsequent panels have a consistent container to render inside.
**Expected Outcomes:**
- Terminal design tokens applied globally: `#000000` background, accent colors, JetBrains Mono + Inter typography
- `DashboardShell.tsx` renders: Sidebar, Header, TickerTape placeholder, React Grid Layout panel grid
- Panels are draggable, resizable, and persist layout to `layoutStore` (localStorage)
- All shadcn/ui primitives overridden with terminal aesthetic
- Responsive breakpoints: full desktop (primary), tablet (degraded), mobile (view-only)
- Framer Motion page transitions and panel mount animations

**Todo List:**
1. Define full Tailwind design token set in `tailwind.config.ts` and `globals.css`
2. Install and configure JetBrains Mono and Inter via `next/font`
3. Build `Sidebar.tsx` with navigation items and collapse behavior
4. Build `Header.tsx` with symbol search (debounced, calls `/market/search`), user menu
5. Build `PanelGrid.tsx` wrapping React Grid Layout with layout persistence
6. Build placeholder panel wrapper component with title bar, close/minimize controls
7. Build `TickerTape.tsx` with Framer Motion horizontal scroll animation (static mock data initially)
8. Override all shadcn/ui primitives for terminal theme
9. Write Storybook stories (optional) or visual regression snapshots for design tokens

**Relevant Context:** React Grid Layout requires `"use client"` — App Router architecture means panel grid is a client component within a server component shell layout.
**Status:** `[ ] pending`

---

### Sub-Task 5 — Market Data Layer and WebSocket Infrastructure
**Intent:** Implement the full data ingestion pipeline, provider abstraction, and WebSocket fan-out so real-time prices flow from external APIs to connected dashboard clients.
**Expected Outcomes:**
- At least two live market data providers implemented (Alpaca + yfinance fallback)
- OHLCV bars persisted to TimescaleDB on schedule
- Latest quotes written to Redis and published to `channel:quotes`
- `GET /api/v1/market/bars/{symbol}` returns paginated OHLCV from TimescaleDB
- `GET /api/v1/market/quotes` returns batch latest quotes from Redis
- `WS /ws/market` accepts symbol subscriptions and streams real-time quotes

**Todo List:**
1. Implement `services/market_data/base.py` abstract interface
2. Implement `services/market_data/alpaca.py` (WebSocket + REST)
3. Implement `services/market_data/yahoo_finance.py` (polling fallback)
4. Implement `services/market_data/router.py` provider selection
5. Implement `data/ingestion/normalizer.py` canonical OHLCV schema
6. Implement `data/ingestion/writer.py` TimescaleDB writer
7. Implement `data/ingestion/scheduler.py` APScheduler jobs
8. Implement `data/cache/quote_cache.py` and `data/cache/pubsub.py`
9. Implement `api/v1/market.py` REST endpoints
10. Implement `api/ws/market_feed.py` WebSocket handler
11. Implement `frontend/src/hooks/useWebSocket.ts` and `useMarketData.ts`
12. Wire `marketDataStore` to WebSocket

**Relevant Context:** All external API keys come from environment variables. API provider list and their tiers are documented in the Technology Stack section.
**Status:** `[ ] pending`

---

### Sub-Task 6 — Candlestick Chart Panel
**Intent:** Build the flagship ChartPanel with TradingView Lightweight Charts, all timeframes, all indicators, and drawing tools.
**Expected Outcomes:**
- ChartPanel renders live OHLCV candlesticks for any selected symbol
- ChartToolbar allows: symbol change, timeframe selection (1m/5m/15m/1h/4h/1D/1W), chart type (candlestick/Heikin-Ashi/line/area/bar/baseline), indicator picker
- All trend, momentum, volatility, volume, and structure indicators implemented and toggleable
- Drawing tools: trendlines, Fibonacci retracement/extension, horizontal/vertical lines, channels, text annotations
- Chart updates in real-time from `useMarketData` WebSocket subscription
- Multi-timeframe panel (MTFPanel) renders 6 mini charts simultaneously

**Todo List:**
1. Implement all TypeScript indicator compute functions in `src/lib/indicators/`
2. Implement `ChartCanvas.tsx` mounting TradingView Lightweight Charts with `useEffect`
3. Implement `ChartToolbar.tsx` with indicator picker dropdown
4. Implement `IndicatorOverlay.tsx` rendering active indicators as series/panes
5. Implement `DrawingTools.tsx` with trendline and Fibonacci tools
6. Implement `DrawingManager.ts` serializing drawing state to `chartStore`
7. Implement `MTFPanel` with 6 `MiniChart` instances
8. Wire chart to real-time data from `useMarketData`
9. Implement Heikin-Ashi OHLCV transform
10. Write unit tests for all indicator compute functions

**Relevant Context:** TradingView Lightweight Charts is canvas-based — all custom indicator rendering must use its `ISeriesApi` primitive. Complex indicators (Volume Profile, IV Surface) may need D3.js overlay on a separate canvas element layered over the chart.
**Status:** `[ ] pending`

---

### Sub-Task 7 — Watchlist Panel and Ticker Tape
**Intent:** Build the two real-time data panels that frame the top of the dashboard.
**Expected Outcomes:**
- WatchlistPanel shows: symbol, last price, change ($), change (%), volume, sparkline — all updating live
- Users can add/remove symbols, create multiple watchlists (persisted to PostgreSQL)
- Ticker tape scrolls continuously across the top, showing live price + change for all watched symbols
- All updates flow through `marketDataStore` WebSocket (no duplicate connections)

**Todo List:**
1. Implement `api/v1/watchlist.py` CRUD endpoints
2. Implement `WatchlistPanel/index.tsx` with TanStack Table (virtualized rows)
3. Implement `WatchlistRow.tsx` with Framer Motion price flash animation on update
4. Implement `Sparkline.tsx` micro-chart using Recharts
5. Implement `WatchlistSearch.tsx` using `/market/search` endpoint with debounce
6. Implement `TickerTape.tsx` with CSS marquee animation driven by `marketDataStore`
7. Implement `watchlistStore.ts` with localStorage persistence
8. Wire watchlist symbols to WebSocket subscription management

**Status:** `[ ] pending`

---

### Sub-Task 8 — News Feed and Sentiment Scoring
**Intent:** Build the complete news ingestion, NLP scoring pipeline, and NewsFeedPanel.
**Expected Outcomes:**
- News articles ingested from at least 2 sources (NewsAPI + Benzinga)
- FinBERT scores every article in a Celery worker (asynchronous, non-blocking)
- spaCy NER extracts ticker mentions
- High-impact articles (earnings, Fed, M&A) forwarded to GPT-4o scorer
- Per-article sentiment badge visible in NewsFeedPanel: label, confidence, impact category
- Per-ticker aggregate sentiment score available at `/news/sentiment/{symbol}`
- AIScorePanel shows aggregate score with time-decay visualization

**Todo List:**
1. Implement `services/news/newsapi.py` and `services/news/benzinga.py`
2. Implement `services/news/aggregator.py`
3. Download and cache FinBERT model (ProsusAI/finbert from HuggingFace)
4. Implement `services/sentiment/finbert.py`
5. Implement `services/sentiment/ner_extractor.py`
6. Implement `services/sentiment/openai_scorer.py` with impact-gating logic
7. Implement `services/sentiment/aggregator.py` with time-decay weighting
8. Implement Celery tasks in `tasks/sentiment_tasks.py`
9. Implement `api/v1/news.py` endpoints
10. Implement `NewsFeedPanel` with SentimentBadge and filtering
11. Implement `AIScorePanel` with confidence gauge

**Relevant Context:** OpenAI API key must come from environment variable `OPENAI_API_KEY`. Add prominent UI disclaimer: "AI sentiment scores are not investment advice."
**Status:** `[ ] pending`

---

### Sub-Task 9 — Portfolio, Options, Order Book, and Risk Panels
**Intent:** Build all remaining core panels: portfolio overview, positions, options chain, Level 2, time & sales, and risk metrics.
**Expected Outcomes:**
- PortfolioPanel shows equity, cash, unrealized P&L, realized P&L, drawdown meter
- OptionsChainPanel shows full chain with Delta, Gamma, Theta, Vega, Rho, IV, OI for any expiry
- OrderBookPanel shows live bid/ask ladder with size visualization
- TimeAndSalesPanel streams trade prints in real-time
- RiskPanel shows VaR, CVaR, Sharpe, Sortino, Beta, Alpha with position sizing calculator

**Todo List:**
1. Implement options chain fetch + Greeks compute in `services/options/`
2. Implement `api/v1/options.py`, `api/ws/orderbook_feed.py`, `api/ws/tape_feed.py`
3. Implement `api/v1/portfolio.py` and `services/risk/` modules
4. Build `PortfolioPanel` components
5. Build `OptionsChainPanel` with expiry selector and calls/puts table
6. Build `OrderBookPanel` with `BidAskLadder.tsx` (color-coded bar visualization)
7. Build `TimeAndSalesPanel` with virtualized scrolling trade list
8. Build `RiskPanel` with all ratio displays and position sizing calculator

**Status:** `[x] complete`

---

### Sub-Task 10 — Screener, Alerts, Macro, Heat Maps, and Crypto Panels
**Intent:** Complete all remaining secondary and advanced panels from the spec.
**Expected Outcomes:**
- ScreenerPanel: users build multi-condition filters (fundamental + technical), results update live
- AlertsPanel: full CRUD for price/indicator/news/P&L alerts; triggered alerts pushed via WebSocket
- MacroPanel: yield curve chart (D3.js), VIX/DXY tiles, CPI/GDP from FRED
- HeatMapPanel: S&P 500 sector treemap with color-coded % change (D3.js)
- CorrelationMatrix: heatmap of pairwise correlations for watched symbols
- CryptoPanel: funding rates, on-chain metrics, liquidation heatmap
- EconomicCalendarPanel: upcoming events with impact filter
- DarkPoolPanel: unusual options activity table

**Todo List:**
1. Implement `services/screener/engine.py` with fundamental + technical filters
2. Implement `services/macro/fred.py` and `services/macro/yield_curve.py`
3. Implement `services/alerts/evaluator.py` and `services/alerts/dispatcher.py`
4. Implement `api/v1/screener.py`, `api/v1/alerts.py`, `api/v1/macro.py`, `api/v1/calendar.py`, `api/v1/crypto.py`
5. Implement `api/ws/alerts_feed.py`
6. Build all panel components in `frontend/src/components/panels/`
7. Implement D3.js heat map and correlation matrix visualizations

**Status:** `[ ] pending`

---

### Sub-Task 11 — Hardening, Security Audit, and CI/CD Finalization
**Intent:** Ensure the platform meets enterprise security and operational standards before any wider use.
**Expected Outcomes:**
- All secrets verified to come from environment variables only
- Bandit (Python SAST) and ESLint security plugin run in CI with zero high-severity findings
- All API endpoints protected by JWT auth and RBAC
- Audit log records all auth events and sensitive data access
- Rate limiting enforced at NGINX and FastAPI middleware level
- Prometheus metrics exposed; Grafana dashboard for service health
- Complete `.env.example` with all required variables documented

**Todo List:**
1. Run Bandit on all Python code; fix all high/medium findings
2. Add `eslint-plugin-security` to frontend; fix all warnings
3. Verify all FastAPI routes have auth dependency injected
4. Wire `audit_log` writes to all auth, portfolio, and alert mutation endpoints
5. Configure NGINX rate limiting (`limit_req_zone`)
6. Add FastAPI middleware for request rate limiting (Redis-backed)
7. Instrument FastAPI with `prometheus-fastapi-instrumentator`
8. Build Grafana dashboard for: request rate, WebSocket connections, Celery queue depth, DB query latency
9. Final review of all `.env.example` entries

**Status:** `[ ] pending`

---

*Plan written. Ready for review.*
