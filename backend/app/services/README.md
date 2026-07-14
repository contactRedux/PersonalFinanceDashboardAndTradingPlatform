# backend/app/services — Business Logic

## What is this folder?

Services are where the actual work happens. Think of each subfolder as a specialist department in a company:
- The `market_data/` department knows how to fetch stock prices from various providers
- The `alerts/` department knows how to evaluate whether a price has crossed a threshold
- The `sentiment/` department knows how to read a news headline and decide if it's bullish or bearish

API handlers in `app/api/v1/` call these services. The handlers are thin wrappers — they just receive a request, call a service, and return the result.

---

## Services Overview

| Folder | What it does |
|---|---|
| `market_data/` | Fetch live quotes and historical OHLCV bars from Alpaca, yFinance, etc. |
| `alerts/` | Evaluate alert conditions against current prices; classify impact |
| `sentiment/` | Score news text with FinBERT + optional GPT-4o; aggregate scores per ticker |
| `news/` | Fetch articles from Benzinga, NewsAPI, Reddit, SEC EDGAR, Twitter/X |
| `orders/` | Place and cancel paper trades via Alpaca REST API |
| `options/` | Fetch options chains (calls and puts) via Polygon.io |
| `indicators/` | Technical indicator calculations (used for alert evaluation) |
| `screener/` | Filter stocks by criteria (P/E ratio, volume, RSI range, etc.) |
| `macro/` | Fetch macroeconomic data from FRED (Federal Reserve Economic Data) |
| `crypto/` | Cryptocurrency prices from Binance and CoinGecko |
| `risk/` | Portfolio risk calculations (Value at Risk, position sizing) |
| `audit/` | Write entries to the append-only audit log |

---

## Most Important Code

### `market_data/`

**`AlpacaProvider`** in [`market_data/alpaca.py`](market_data/alpaca.py) — The primary data source. Implements three key methods:

- **`get_bars(symbol, timeframe, start, end)`** — Fetches historical OHLCV candlestick data from Alpaca's REST API. Supports timeframes from 1-minute to weekly.
- **`get_quotes(symbols)`** — Fetches the latest bid/ask/price for a list of tickers in a single API call.
- **`stream_quotes(symbols)`** — Opens a WebSocket connection to Alpaca and yields live quote updates as they arrive. Automatically reconnects if the connection drops.

**`get_provider()`** in [`market_data/router.py`](market_data/router.py) — Returns the configured data provider (Alpaca if keys are present, otherwise Yahoo Finance as a free fallback). This means the rest of the code doesn't need to know *which* provider is being used.

### `alerts/`

**`evaluate_price_alert(condition, quote)`** — Takes an alert condition (e.g. "price ≥ 200") and the current market data for a symbol, and returns a triggered event if the condition is met. Used by the `evaluate_alerts` Celery task.

### `sentiment/`

**FinBERT scoring** in `sentiment/finbert.py` — Loads the `ProsusAI/finbert` model from HuggingFace and classifies text as `positive`, `negative`, or `neutral` with a confidence score. FinBERT is a version of BERT (Bidirectional Encoder Representations from Transformers — a language model pre-trained on billions of words) that has been fine-tuned specifically on financial news.

**`score_article` pipeline** (orchestrated in `app/tasks/sentiment_tasks.py`):
1. Run FinBERT on headline + body
2. Extract mentioned tickers using NER (Named Entity Recognition — finding proper nouns like company names)
3. If the article is high-impact (earnings, Fed decision), optionally invoke GPT-4o for a richer score
4. Combine scores with 40% FinBERT / 60% GPT-4o weighting
5. Save to MongoDB; update per-ticker sentiment aggregate in Redis

---

## How does this connect to the rest of the app?

- `app/api/v1/` handlers import and call these services
- `app/tasks/` Celery jobs also call these services directly (they share the same Python process as the API on startup, but workers run separately)
- Services talk to external APIs (Alpaca, Polygon, FRED, OpenAI) using the `httpx` async HTTP client
- Quotes returned from `market_data/` are cached in Redis by the `quote_cache` helper before being returned to the API caller
