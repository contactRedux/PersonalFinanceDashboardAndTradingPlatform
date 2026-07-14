# frontend/components/panels — The 23 Dashboard Panels

## What is this folder?

Each subfolder here is one panel that appears on the main trading dashboard. Every panel is an independent React component — it fetches its own data, manages its own state, and can be shown/hidden/resized without affecting other panels.

Think of each panel like an app on a smartphone home screen. They're all independent, but they live on the same screen.

---

## The Panels — Plain English Descriptions

### 📈 ChartPanel
The main interactive candlestick chart. A **candlestick** is a common way to show price movement: each candle shows the opening price, closing price, and the highest/lowest prices during a time period. Powered by TradingView Lightweight Charts. Supports switching between timeframes (1-minute up to weekly), overlaying indicator lines, and zooming/panning.

### 👁 WatchlistPanel
Your list of tracked symbols with live prices. Type a ticker (e.g. `AAPL`) to add it. Each row shows the symbol, current price (updating live), change since yesterday's close (in dollars and percentage), and a sparkline mini-chart of recent price history.

### 💼 PortfolioPanel
Shows your current holdings: which stocks/crypto you own, how many shares, average buy price, current value, and P&L (Profit and Loss — how much you're up or down). Fetches data from `/api/v1/portfolio`.

### 📰 NewsFeedPanel
A real-time news feed aggregating articles from multiple sources (Benzinga, NewsAPI, Reddit, SEC filings). Each headline shows a colored sentiment badge: 🟢 bullish / 🔴 bearish / ⚪ neutral, scored by FinBERT.

### 📖 OrderBookPanel
Shows the **Level 2 order book** — a live list of all buy orders (bids) and sell orders (asks) waiting to be filled, with price and quantity. The spread (gap between the best bid and best ask) is highlighted. Updated in real time via the `/ws/orderbook/{symbol}` WebSocket.

### 🖨️ TimeAndSalesPanel
The "tape" — a live scrolling list of every individual trade that just printed, showing the price, quantity, and direction (buy-side / sell-side). Updated via the `/ws/tape` WebSocket. Used to watch order flow in real time.

### ⚠️ RiskPanel
Portfolio risk metrics: Value at Risk (VaR — the maximum expected loss on a bad day at a given confidence level), position concentration, and exposure by sector.

### 📊 OptionsChainPanel
Displays the **options chain** for a symbol — a table of all available option contracts (calls and puts at various strike prices and expiration dates). An **option** gives the holder the right (but not obligation) to buy or sell a stock at a set price before a set date. Data from Polygon.io.

### 🔍 ScreenerPanel
Filter the entire market by criteria: P/E ratio range, market cap, volume spike, RSI below 30, sector, etc. Think of it like a search engine for stocks. Results update when you change a filter.

### 🔔 AlertsPanel
Create, view, and manage price alerts. Set a condition ("NVDA price > $900") and a message. When the condition triggers, a notification appears instantly in this panel (and optionally as a browser notification).

### 🌍 MacroPanel
Macroeconomic indicators from the Federal Reserve (FRED): Fed Funds Rate, inflation (CPI), GDP growth, unemployment rate, 10-year Treasury yield. These are the big-picture economic numbers that influence all markets.

### 📅 EconomicCalendarPanel
Upcoming economic events with impact ratings (high/medium/low). Shows the event name, scheduled time, the market's forecast, and the previous reading. High-impact events (Fed meetings, jobs reports) are highlighted in red.

### 🗺 HeatMapPanel
A color-coded grid showing all major stocks and sectors at a glance. Green = up today, red = down. Larger squares = larger market cap. Lets you see sector rotation (money moving from one industry to another) at a glance.

### 🔗 CorrelationMatrixPanel
A grid showing how closely pairs of stocks or assets move together on a scale of -1 (always opposite) to +1 (always together). Useful for diversification — you want assets with low correlation so they don't all drop at once.

### 🏊 DarkPoolPanel
Large **dark pool** trades — institutional block trades that happen off-exchange and are reported after the fact. Unusually large prints can signal big-money positioning.

### ₿ CryptoPanel
Live cryptocurrency prices (Bitcoin, Ethereum, etc.) from Binance/CoinGecko with 24h change, volume, and market cap.

### 📉 PerformancePanel
Historical performance charts for your portfolio: equity curve, drawdown chart, rolling Sharpe ratio over time.

### ⏱️ MultiTimeframePanel
Shows the same symbol's chart simultaneously across multiple timeframes (e.g. 1-hour, 4-hour, and daily) side by side, helping you confirm signals across different time horizons.

### 🛒 OrderEntryPanel
A form to place paper trades: symbol, side (buy/sell), quantity, order type (market/limit/stop), and price. Sends orders to Alpaca paper trading via `POST /api/v1/orders`. Filled orders update the portfolio in real time.

### ⏪ BacktestPanel
An interactive backtesting form: choose a strategy, ticker, date range, and parameters. Click "Run" to see an equity curve and performance report right in the dashboard. Also has a "Bayesian Optimize" button to auto-find the best parameters.

### 📊 VolatilityPanel
Implied volatility (IV — the market's forecast of how much a stock will move, derived from option prices) and historical volatility charts. Shows the **volatility surface** — how IV varies by strike price and expiration date.

### 📒 TradeJournalPanel
AI-generated notes for each completed trade, written by GPT-4o or Claude: entry/exit rationale, market conditions at the time, and suggested improvements.

### 🏗️ StrategyBuilderPanel
A visual, drag-and-drop strategy builder. Connect indicator nodes (SMA, RSI, MACD) and logic nodes (AND, threshold crossover) to build trading rules without writing code. The node graph is saved to the database as JSON and can be sent directly to the backtest engine.

---

## How does this connect to the rest of the app?

- Panels subscribe to live data via the shared `useMarketData()` hook, which writes to `marketDataStore` — they never open their own WebSocket connections
- Panels call REST endpoints via functions in `lib/api/` for historical or on-demand data
- Panel visibility and grid positions are controlled by `store/layoutStore`
- The `PanelGrid` component in `components/layout/` renders all visible panels
