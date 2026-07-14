# frontend/lib — Utility Functions and API Clients

## What is this folder?

This folder contains the "toolbox" — shared functions that multiple panels and components use. There are three main categories:

1. **API clients** (`api/`) — functions for talking to the backend server
2. **Indicators** (`indicators/`) — financial math functions computed in the browser
3. **Formatters** (`formatters.ts`) — functions that turn raw numbers into readable strings

---

## `lib/api/` — Backend Communication

These files are the frontend's "phone book" for the backend. Instead of every component making its own HTTP requests, they all call these shared functions.

**`client.ts`** — The core HTTP client. All API calls go through **`apiRequest<T>(path, options?)`**, which:
1. Adds the `Authorization: Bearer <token>` header automatically
2. If the access token has expired, automatically calls the refresh endpoint to get a new one (a process called **token rotation** — like silently renewing a library card before it expires)
3. Parses the JSON response and returns it typed as `T`

Exports **`getAccessToken()`**, **`storeTokens(access, refresh)`**, and **`clearTokens()`** for managing JWT tokens stored in `localStorage`.

**`market.ts`** — Functions for fetching price data:
- **`getQuotes(symbols)`** → calls `GET /api/v1/market/quotes`
- **`getBars(symbol, timeframe, options)`** → calls `GET /api/v1/market/bars/{symbol}`
- **`getVPVR(symbol, timeframe)`** → Volume Profile Visible Range (a chart showing at which price levels the most volume traded — the price with the most volume is called the Point of Control, or POC)
- **`searchSymbols(query)`** → symbol search autocomplete

**`websocket.ts`** — URL builders for WebSocket connections:
- **`WS_URLS.market()`** → `/ws/market?token=...`
- **`WS_URLS.orderbook(symbol)`** → `/ws/orderbook/{symbol}?token=...`
- **`WS_URLS.alerts()`** → `/ws/alerts?token=...`

Always appends the access token as a query parameter (WebSocket connections can't send custom HTTP headers like REST calls can).

**`auth.ts`** — Login, register, logout functions
**`portfolio.ts`** — Portfolio positions and P&L
**`options.ts`** — Options chain data
**`screener.ts`** — Stock screener queries

---

## `lib/indicators/index.ts` — Technical Indicator Math

Financial math functions that run entirely in the browser (no server call needed). These are used by the ChartPanel to overlay indicator lines on the price chart.

All functions take arrays of numbers and return arrays of numbers (or objects for multi-line indicators).

| Function | What it calculates |
|---|---|
| **`sma(values, period)`** | SMA (Simple Moving Average) — the plain average of the last N prices |
| **`ema(values, period)`** | EMA (Exponential Moving Average) — like SMA but more weight on recent prices |
| **`macd(close, fast, slow, signal)`** | MACD (Moving Average Convergence Divergence) — a momentum indicator showing when short-term trend diverges from long-term trend. Returns `{macd, signal, histogram}` |
| **`rsi(close, period)`** | RSI (Relative Strength Index, 0-100) — measures whether a stock is overbought (above 70) or oversold (below 30) |
| **`bollingerBands(close, period, stdDev)`** | Bollinger Bands — three lines: a moving average, and bands 2 standard deviations above and below it. When price touches a band, it may revert |
| **`atr(high, low, close, period)`** | ATR (Average True Range) — measures volatility (how much the price typically moves per day) |
| **`vwap(high, low, close, volume)`** | VWAP (Volume-Weighted Average Price) — the average price weighted by trading volume; institutional traders use this as a benchmark |
| **`stochasticRsi(close)`** | Stochastic RSI — combines RSI and stochastic oscillator to measure momentum within the RSI range |
| **`parabolicSar(high, low)`** | Parabolic SAR (Stop and Reverse) — a trailing stop indicator that flips above/below price to signal trend changes |
| **`donchianChannel(high, low, period)`** | Donchian Channel — highest high and lowest low over N periods; breakouts above/below signal trend starts |
| **`keltnerChannel(high, low, close)`** | Keltner Channel — ATR-based bands around an EMA; similar to Bollinger Bands but less sensitive to volatility spikes |

---

## `lib/formatters.ts` — Number Display

Turns raw numbers into human-readable strings:

- **`formatPrice(value)`** → `"192.40"`
- **`formatCurrency(value)`** → `"$1,234.56"`
- **`formatCompact(value)`** → `"1.23B"` or `"456M"`
- **`formatPct(value)`** → `"+1.23%"` or `"-0.45%"`
- **`formatVolume(value)`** → `"55.2M"`
- **`priceChangeClass(change)`** → CSS class name: `"price-up"`, `"price-down"`, or `"price-flat"`

---

## How does this connect to the rest of the app?

- Every panel that fetches data calls a function from `lib/api/`
- `lib/api/client.ts` reads the auth token from `store/authStore` via `getAccessToken()`
- `lib/indicators/` is imported by `ChartPanel` and `MultiTimeframePanel` to draw indicator overlays
- `lib/formatters.ts` is imported by virtually every panel that displays a price or percentage
