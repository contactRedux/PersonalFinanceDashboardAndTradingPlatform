# QuantNexus — Algorithmic Trading Platform

> **Watch live stock prices. Test strategies on 10 years of history. Let AI predict where prices might go. Place paper trades with a single click.**

QuantNexus is an open-source, professional-grade trading platform you can run entirely on your own computer. Think of it as having Bloomberg Terminal features — but free, self-hosted, and hackable.

---

## Key Features

### 📊 Real-Time Market Dashboard
A 23-panel dashboard that updates live. Every panel is resizable and repositionable — drag them around to build the layout that works for you.

- **Live price quotes** with bid/ask spreads, color-coded green/red
- **Interactive candlestick chart** (zoom, pan, multi-timeframe) powered by TradingView Lightweight Charts
- **Order Book** — shows all the buy and sell orders waiting to be filled, like a depth-of-market ladder
- **Time & Sales** (the "tape") — a live stream of every trade that just happened, with price and size
- **Heatmap** — a color grid showing which sectors are up/down right now
- **Correlation Matrix** — shows how closely two stocks move together
- **Volatility Panel** — tracks how wild price swings have been
- **Dark Pool Panel** — large off-exchange block trades reported with a delay
- **Scrolling ticker tape** at the top showing live prices for your watchlist

### 📈 Backtesting Engine
*"What would have happened if I used this strategy over the last 5 years?"*

Replay a strategy against real historical price data. You get a full performance report including:
- **Equity curve** (a chart of your account value over time)
- **Sharpe Ratio** — risk-adjusted return score (higher = better)
- **Maximum Drawdown** — the worst peak-to-trough loss percentage
- **Win rate, profit factor, trade log**
- **Monte Carlo simulation** — runs your strategy 500+ times with randomized trade order to show the range of possible outcomes
- **Walk-Forward Optimization** — tests if a strategy's good parameters hold up on *new* data it hasn't seen before
- Downloadable **PDF and HTML reports**

### 🤖 AI / ML Predictions
Three machine-learning models trained on OHLCV (Open, High, Low, Close, Volume) price data plus technical indicators:

- **LSTM** (Long Short-Term Memory — a type of neural network that reads sequences, like sentences of price data) — predicts whether the next bar will go **up >1%, flat, or down >1%**
- **XGBoost** (a fast, powerful decision-tree ensemble) — outputs a binary **long / no-position** signal plus a confidence score and feature importance ranking
- **HMM** (Hidden Markov Model — a statistical model that finds hidden "states") — classifies the current market **regime**: low volatility, mean-reverting, trending, or high volatility
- **FinBERT** — a finance-specialized language model that reads news headlines and scores them **bullish, bearish, or neutral**
- **GPT-4o** (optional) — used for high-impact news (earnings, Fed decisions) to generate a richer sentiment score

### ⚡ Algorithmic Paper Trading
Place buy/sell orders via the **Alpaca** paper trading API — this uses fake money against real market prices, so you can practice without risk.

- Market, limit, and stop orders
- Real-time order status updates via WebSocket
- Portfolio positions tracked in the database
- AI-generated trade journal entries after each fill

### 📰 News & Sentiment
- Multi-source news feed: Benzinga, NewsAPI, Reddit, SEC EDGAR, Twitter/X
- Each article is automatically scored by FinBERT (and optionally GPT-4o)
- Per-ticker sentiment aggregated over 1h / 4h / 1d windows with time-decay weighting
- Economic Calendar showing upcoming events (FOMC meetings, CPI, GDP releases) with impact ratings

### 🔔 Price Alerts
Set a condition (e.g. "AAPL crosses above $200") and get notified instantly via a WebSocket push to your browser — no polling, no refresh needed.

### 📦 Multi-User Workspaces
Multiple users can log in with separate accounts. Each workspace saves its own panel layout. Roles: `admin`, `trader`, `analyst`, `readonly`.

### 🏗️ Visual Strategy Builder
A drag-and-drop node graph where you connect indicator blocks (SMA, RSI, MACD) and logic blocks (AND, OR, threshold) to build a strategy without writing code. The resulting config is saved as JSON and can be run through the backtester.

---

## Dashboard Layout (ASCII)

```
┌──────────────────────────────────────────────────────────────────┐
│  Ticker Tape:  AAPL $192.40 ▲1.2%   MSFT $415.22 ▼0.3%  ...    │
├──────────────────────────────────────────────────────────────────┤
│ Watchlist  │       Candlestick Chart (7 cols)      │  Portfolio  │
│            │  [AAPL  1D  ▲]  ──────╮──────        │  ─────────  │
│  AAPL ▲    │        /\    /\  /\   │   /\         │  News Feed  │
│  MSFT ▼    │       /  \  /  \/  \_/   /           │             │
│  NVDA ▲    │      /    \/               \_/        │             │
├──────────────────────────────────────────────────────────────────┤
│  Risk Panel  │    Order Book     │    Time & Sales (Tape)        │
├──────────────────────────────────────────────────────────────────┤
│   Options Chain   │    Stock Screener                            │
├──────────────────────────────────────────────────────────────────┤
│  Alerts  │   Macro Indicators   │   Economic Calendar            │
├──────────────────────────────────────────────────────────────────┤
│    Sector Heatmap      │    Correlation Matrix                   │
├──────────────────────────────────────────────────────────────────┤
│   Dark Pool Prints     │    Crypto Panel                         │
├──────────────────────────────────────────────────────────────────┤
│  Performance Charts    │    Multi-Timeframe Panel                │
├──────────────────────────────────────────────────────────────────┤
│  Order Entry  │         Backtesting Panel                        │
├──────────────────────────────────────────────────────────────────┤
│  Volatility Surface    │    Trade Journal                        │
├──────────────────────────────────────────────────────────────────┤
│               Strategy Builder (full width)                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| What it does | Technology |
|---|---|
| User interface (the website you see) | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Charts | TradingView Lightweight Charts |
| App state (memory between panels) | Zustand |
| Backend API server | FastAPI (Python), uvicorn |
| Time-series price database | TimescaleDB (PostgreSQL + extension) |
| Relational data (users, orders, alerts) | PostgreSQL via SQLAlchemy |
| News/sentiment document store | MongoDB |
| Fast cache & real-time pub/sub | Redis |
| Background jobs (training, alerts, sync) | Celery with Redis broker |
| Neural network (LSTM) | PyTorch |
| Gradient-boosted trees (XGBoost) | XGBoost 2.x |
| Market regime detection | hmmlearn (Hidden Markov Model) |
| Finance NLP / sentiment | HuggingFace FinBERT |
| News summarization (optional) | OpenAI GPT-4o / Anthropic Claude |
| Strategy optimization | Optuna (Bayesian TPE sampler) |
| PDF report generation | WeasyPrint |
| Containerization | Docker Compose (dev), Kubernetes (prod) |
| Cloud deployment | Terraform → AWS ECS Fargate |
| Monitoring | Prometheus + Grafana |
| Load testing | k6 |

---

## Prerequisites

| Tool | Minimum version | Where to get it |
|---|---|---|
| Docker Desktop | 4.x | https://www.docker.com/products/docker-desktop/ |
| Node.js | ≥ 20 | https://nodejs.org |
| Python | ≥ 3.11 | https://www.python.org (only needed for local dev without Docker) |
| Git | any | https://git-scm.com |

---

## Quick Start (5 minutes)

```bash
# 1. Get the code
git clone https://github.com/your-org/PersonalFinanceDashboardAndTradingPlatform
cd PersonalFinanceDashboardAndTradingPlatform

# 2. Create your environment file
cp .env.example .env

# 3. Open .env in any text editor and add your free Alpaca paper trading keys
#    Sign up at: https://alpaca.markets  (takes 2 minutes, no credit card)
#    Set ALPACA_API_KEY and ALPACA_SECRET_KEY

# 4. Start everything (downloads ~2 GB of Docker images on first run)
docker compose up -d

# 5. Open the dashboard
#    Visit: http://localhost:3000
#    API docs: http://localhost:8000/api/docs
```

> **What does `docker compose up -d` do?**
> It launches 9 services in the background: the database, Redis cache, MongoDB, the Python API server, a background job worker, the Next.js frontend, an Nginx reverse proxy, Prometheus metrics collector, and Grafana dashboard — all wired together automatically.

---

## Configuration — Environment Variables

Copy `.env.example` to `.env` and fill in the values you need. Most are optional — the platform works in demo mode without any API keys.

| Variable | Plain-English description | Required? |
|---|---|---|
| `ALPACA_API_KEY` | Your Alpaca paper trading key — get one free at [alpaca.markets](https://alpaca.markets) | Recommended |
| `ALPACA_SECRET_KEY` | The matching secret for your Alpaca key | Recommended |
| `ALPACA_BASE_URL` | Use `https://paper-api.alpaca.markets` for fake money, or change to live URL | No |
| `POLYGON_API_KEY` | For options chain data (calls/puts) — [polygon.io](https://polygon.io) | No |
| `FRED_API_KEY` | For macroeconomic indicators (GDP, CPI, Fed Funds Rate) — free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/fred/) | No |
| `OPENAI_API_KEY` | Enables GPT-4o news summarization and trade journal AI | No |
| `ANTHROPIC_API_KEY` | Alternative to OpenAI for AI features | No |
| `NEWSAPI_KEY` | Pulls live financial news from [newsapi.org](https://newsapi.org) | No |
| `BENZINGA_API_KEY` | Professional-grade financial news | No |
| `BINANCE_API_KEY` + `BINANCE_SECRET_KEY` | For live crypto price feeds from Binance | No |
| `JWT_SECRET_KEY` | A random secret string used to sign login tokens — **must be changed in production** | Yes |
| `DATABASE_URL` | PostgreSQL connection string — pre-filled for Docker | Yes |
| `REDIS_URL` | Redis connection string — pre-filled for Docker | Yes |

---

## How to Use — 5 Main Workflows

### 1. Watching Live Prices
1. Log in at `http://localhost:3000`
2. Type a stock ticker (e.g. `AAPL`) into the Watchlist panel search box
3. Click "Add" — the ticker appears in the list with a live price that updates every second
4. Click the ticker name to load it into the main Chart panel

### 2. Running a Backtest
1. Scroll down to the **Backtesting Panel**
2. Enter a ticker, select a date range (e.g. 2020-01-01 to 2024-01-01), pick a strategy (e.g. `sma_cross`)
3. Click **Run Backtest** — results appear within seconds
4. Scroll down to see the equity curve, trade log, and performance stats
5. Click **Download PDF Report** for a printable version

### 3. Setting a Price Alert
1. Find the **Alerts Panel**
2. Click **New Alert**, enter the symbol, choose a condition (e.g. "price ≥ 200"), and a message
3. Click **Save** — the alert is active immediately
4. When the price crosses your threshold, a notification appears in the Alerts panel in real time (no refresh needed)

### 4. Training an ML Model
1. Call the API: `POST http://localhost:8000/api/v1/ml/lstm/train` with body `{"ticker": "AAPL", "start": "2020-01-01", "end": "2024-01-01"}`
2. The training job runs in the background (takes 1-5 minutes depending on your hardware)
3. Call `GET http://localhost:8000/api/v1/ml/lstm/predict?ticker=AAPL` to get a prediction: up / flat / down with probabilities

### 5. Placing a Paper Trade
1. Scroll to the **Order Entry Panel**
2. Type a ticker symbol, choose Buy or Sell, enter a quantity, select order type (Market / Limit / Stop)
3. Click **Submit Order** — the order is sent to Alpaca's paper trading environment
4. The order status updates live in the Order Book panel as it goes from `pending` → `submitted` → `filled`

---

## Project Structure

```
PersonalFinanceDashboardAndTradingPlatform/
├── backend/          FastAPI server — all API endpoints, data, business logic
├── frontend/         Next.js 15 user interface — the dashboard you see
├── backtesting/      Strategy backtesting engine and built-in strategies
├── ml/               Machine learning models (LSTM, XGBoost, HMM)
├── infra/            Infrastructure: Docker configs, Kubernetes, Terraform (AWS)
├── docs/             Architecture docs, ADRs, developer guides
├── tests/            Load tests (k6) and E2E test placeholders
├── engine/           Future C++ high-performance execution engine (planned)
├── data/             Persisted ML model weights (created at runtime)
├── docker-compose.yml  One command to start everything locally
├── Makefile          Shortcut commands: make dev, make test, make lint
└── .env.example      Copy to .env — fill in your API keys
```

---

## Running Tests

```bash
# Run all tests (backend Python + frontend TypeScript)
make test

# Backend only (pytest)
make test-backend

# Frontend only (Vitest unit tests)
make test-frontend

# End-to-end tests (Playwright — requires the app to be running)
make test-e2e

# Load tests — simulates 1,000 concurrent WebSocket users (requires k6)
make load-test
```

---

## API Documentation

When the server is running, interactive API docs are available at:

**`http://localhost:8000/api/docs`** — click any endpoint to try it live

| Endpoint | What it does |
|---|---|
| `POST /api/v1/auth/register` | Create a new user account |
| `POST /api/v1/auth/login` | Log in, get JWT access tokens |
| `GET /api/v1/market/quotes?symbols=AAPL,MSFT` | Get latest prices for multiple tickers |
| `GET /api/v1/market/bars/AAPL?timeframe=1d` | Get OHLCV candlestick bars |
| `GET /api/v1/market/indicators/AAPL` | Get RSI, MACD, Bollinger Bands values |
| `POST /api/v1/backtest/run` | Run a backtest with a strategy and date range |
| `POST /api/v1/backtest/optimize` | Find the best strategy parameters (Bayesian search) |
| `POST /api/v1/ml/lstm/train` | Train the LSTM model for a ticker (async job) |
| `GET /api/v1/ml/lstm/predict` | Get LSTM up/flat/down prediction |
| `POST /api/v1/alerts` | Create a price or indicator alert |
| `GET /api/v1/news` | Get recent news articles with sentiment scores |
| `POST /api/v1/orders` | Place a paper trade via Alpaca |
| `WS /ws/market` | WebSocket: subscribe to live quote stream |
| `WS /ws/alerts` | WebSocket: receive triggered alert notifications |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes, following existing code style
4. Run `make lint` and `make test` — both must pass with no new errors
5. Open a pull request with a clear description

See [`docs/adr/`](docs/adr/) for Architecture Decision Records that explain *why* key decisions were made.

---

## License

MIT — see `LICENSE` file. Free to use, modify, and distribute.

---

## Key Links at a Glance

| What | URL (local) |
|---|---|
| Dashboard | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| Grafana Monitoring | http://localhost:3001 (admin / changeme) |
| Prometheus Metrics | http://localhost:9090 |
