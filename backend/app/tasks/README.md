# backend/app/tasks — Background Jobs

## What is this folder?

Background tasks are jobs that run *outside* the normal request/response cycle — they run in a separate process on a schedule or when triggered, without making the user wait.

Think of them like a dishwasher running in the background while a restaurant keeps serving tables. The chef (API) doesn't stop to wash dishes — a separate worker handles that.

QuantNexus uses **Celery** (a popular Python task queue) with **Redis** as the message broker (the intermediary that delivers tasks to workers). When a task is "dispatched," a message is written to Redis, and the Celery worker process picks it up and runs it.

---

## Files

| File | Tasks inside | What they do |
|---|---|---|
| `celery_app.py` | — | Creates and configures the Celery application; sets up the beat schedule (which tasks run automatically and how often) |
| `data_tasks.py` | `refresh_ohlcv`, `record_ticks` | Fetch new price bars from Alpaca and store them in TimescaleDB; stream individual trades into the `ticks` table |
| `alert_tasks.py` | `evaluate_alerts` | Scan all active alerts, compare against current Redis-cached prices, mark triggered alerts, push notifications via WebSocket |
| `ml_tasks.py` | `train_lstm_task`, `train_xgboost_task` | Train ML models in the background (so heavy computation doesn't freeze the API server) |
| `order_tasks.py` | `sync_open_orders` | Poll Alpaca every 10 seconds for order status changes; update the database; push fills to the WebSocket |
| `sentiment_tasks.py` | `score_article`, `update_ticker_sentiment_aggregate` | Score a news article with FinBERT + GPT-4o; recompute the time-weighted sentiment aggregate for a ticker |
| `fill_tasks.py` | `handle_order_fill` | When an order is filled, update the portfolio positions table |
| `journal_tasks.py` | `analyze_trade` | After a fill, use AI to generate a trade journal entry summarizing the trade rationale |

---

## Most Important Tasks

**`evaluate_alerts()`** in [`alert_tasks.py`](alert_tasks.py) — Runs every minute. Loads all active, untriggered alerts from PostgreSQL, batch-fetches current prices from Redis, checks each condition, and for any trigger: marks the alert as triggered in the DB, then publishes a message to the Redis `channel:alerts:{user_id}` pub/sub channel so the `/ws/alerts` WebSocket feed immediately notifies that user's browser.

**`refresh_ohlcv(symbol, timeframe)`** in [`data_tasks.py`](data_tasks.py) — Fetches the last 365 days of price bars for a symbol, writes them to the `ohlcv` TimescaleDB hypertable, and publishes an `ohlcv_refreshed` event so connected chart panels can refresh. Has exponential backoff retry logic (waits 5s, then 10s, then 20s between attempts).

**`train_lstm_task(ticker, start, end, epochs)`** in [`ml_tasks.py`](ml_tasks.py) — Invokes `ml/models/lstm/train.py` in the background. Training a neural network can take minutes — running it here means the API endpoint returns immediately with a job ID, and the user can check progress rather than waiting for the HTTP request to complete.

**`score_article(article)`** in [`sentiment_tasks.py`](sentiment_tasks.py) — A 7-step pipeline: FinBERT score → ticker extraction → impact classification → optional GPT-4o → composite score → MongoDB save → per-ticker aggregate update. The `max_retries=3` setting means it automatically retries up to 3 times if a step fails (e.g. a temporary OpenAI API error).

---

## Beat Schedule

The Celery beat scheduler (like a cron job manager) runs these tasks automatically:

| Task | Frequency | Purpose |
|---|---|---|
| `evaluate_alerts` | Every 60 seconds | Check all price alerts |
| `refresh_ohlcv` | Every 5 minutes | Keep price bars fresh |
| `sync_open_orders` | Every 10 seconds | Sync paper trade order status |

---

## How does this connect to the rest of the app?

- Tasks are dispatched (queued) by API handlers using `.delay()` — for example, `train_lstm_task.delay("AAPL", "2020-01-01", "2024-01-01")`
- Tasks communicate results back to users via Redis pub/sub → WebSocket feeds in `app/api/ws/`
- The Celery **worker** and the Celery **beat scheduler** both run as separate Docker containers (see `docker-compose.yml`), but they share the same `backend/` codebase
