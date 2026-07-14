# backend/app/api — API Endpoints

## What is this folder?

This folder contains every URL that the backend exposes — both regular HTTP endpoints (REST API) and real-time WebSocket connections. Think of it as the menu in a restaurant: it lists everything you can order and what you get back.

---

## Structure

```
api/
├── v1/          REST API (version 1) — standard request/response
│   ├── router.py      Registers all v1 sub-routers under /api/v1/
│   ├── auth.py        Login, register, refresh tokens, TOTP setup
│   ├── market.py      Quotes, OHLCV bars, indicators, VPVR
│   ├── backtest.py    Run backtests, optimize strategies, download PDF report
│   ├── ml.py          Train LSTM/XGBoost, get predictions, feature importance
│   ├── alerts.py      Create, list, delete price/indicator alerts
│   ├── orders.py      Place and list paper trades via Alpaca
│   ├── portfolio.py   Portfolio positions, P&L summary
│   ├── news.py        News feed with FinBERT sentiment scores
│   ├── options.py     Options chain (calls/puts) via Polygon.io
│   ├── screener.py    Filter stocks by fundamental and technical criteria
│   ├── watchlist.py   Manage personal symbol watchlists
│   ├── workspaces.py  Create and manage multi-user workspaces
│   ├── strategies.py  Save/load visual strategy builder configs
│   ├── journal.py     AI-generated trade journal entries
│   ├── calendar.py    Upcoming economic events (FOMC, CPI, earnings)
│   ├── crypto.py      Cryptocurrency prices via Binance/CoinGecko
│   └── macro.py       Macroeconomic indicators via FRED
└── ws/          WebSocket feeds — real-time streaming
    ├── router.py      Registers all WebSocket routes under /ws/
    ├── market_feed.py /ws/market — subscribe to live quote updates
    ├── orderbook_feed.py /ws/orderbook/{symbol} — Level 2 order book
    ├── tape_feed.py   /ws/tape — real-time Time & Sales prints
    ├── alerts_feed.py /ws/alerts — triggered alert notifications
    └── orders_feed.py /ws/orders — order status change notifications
```

---

## Most Important Endpoints

### REST — Key Endpoints

**`GET /api/v1/market/quotes?symbols=AAPL,MSFT`** — Returns the latest price, bid, ask, volume, and change percentage for one or more tickers. Checks Redis cache first (60-second TTL); falls back to live Alpaca API if stale.

**`GET /api/v1/market/bars/{symbol}?timeframe=1d`** — Returns OHLCV (Open, High, Low, Close, Volume — the standard candlestick data) bars for any timeframe from 1-minute to weekly.

**`GET /api/v1/market/indicators/{symbol}`** — Returns pre-computed technical indicator values (SMA-20, EMA-50, RSI-14, MACD signal, Bollinger Bands upper/lower) cached in Redis for 5 minutes.

**`POST /api/v1/backtest/run`** — Runs a full backtest. Send a ticker, date range, strategy name, and parameters; get back an equity curve, full trade log, and all performance metrics (Sharpe ratio, max drawdown, win rate, etc.).

**`POST /api/v1/backtest/optimize`** — Runs Bayesian optimization (using Optuna — a smart parameter search library) to find the best parameter values for a strategy. Much faster than trying every combination.

**`POST /api/v1/ml/lstm/train`** — Queues a background job (via Celery) to train the LSTM neural network on historical data for a ticker. Returns a job ID immediately; training runs in the background.

### WebSockets — Real-Time Feeds

**`WS /ws/market`** — After connecting, send `{"action": "subscribe", "symbols": ["AAPL", "BTC-USD"]}`. The server will push a message every time those prices update.

**`WS /ws/alerts`** — Delivers a real-time notification the moment a price alert you set is triggered — no need to refresh the page.

---

## How does this connect to the rest of the app?

- Every REST handler in `v1/` calls into `app/services/` for actual data fetching and processing — the handlers themselves are intentionally thin
- WebSocket feeds in `ws/` subscribe to Redis pub/sub channels; the backend publishes updates to those channels from Celery tasks and the data ingestion scheduler
- All endpoints require a valid JWT (JSON Web Token) — the `CurrentUser` dependency in `app/dependencies.py` handles token verification automatically
- The frontend calls these endpoints via `frontend/lib/api/` (REST) and `frontend/lib/api/websocket.ts` (WebSocket)
