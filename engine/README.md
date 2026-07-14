# engine/ — Future C++ Execution Engine

## What is this folder?

This folder is reserved for a future high-performance **trade execution engine** written in C++.

Currently, it is empty. No C++ code has been written yet.

---

## What Will It Be?

### The Problem It Will Solve

The Python backtesting engine in `backtesting/` is excellent for daily and hourly bar data. But as QuantNexus evolves toward **high-frequency** and **intraday** trading (strategies that make hundreds of decisions per second), Python's speed becomes a bottleneck.

Think of it this way: Python is like a skilled chef who can cook almost anything — but for a factory that needs to produce 10,000 identical sandwiches per second, you bring in specialized machinery. That machinery is what the C++ engine will be.

---

## What It Will Do When Built

The planned C++ execution engine will handle:

1. **Ultra-Low Latency Order Routing** — Submitting orders in microseconds (millionths of a second) rather than milliseconds. For strategies where being first matters, every microsecond counts.

2. **Tick-by-Tick Backtesting** — Replaying individual trade prints from the `ticks` database table, rather than OHLCV bars. This allows strategies to be tested at the same granularity at which they would execute in production.

3. **FIX Protocol** — FIX (Financial Information eXchange — the standard messaging format used by brokers and exchanges for order submission and market data) support for connecting to institutional-grade execution venues, not just retail APIs like Alpaca.

4. **Lock-Free Order Book** — A data structure that maintains the full Level 2 order book (all bids and asks at all price levels) without blocking other threads — essential for sub-millisecond strategy decisions.

5. **Python Bridge** — A Python binding (likely via `pybind11` or a REST/socket API) so that strategies and ML models written in Python can still send signals to the C++ engine for actual execution.

---

## Expected Architecture

```
Python Strategy Layer
  (signals from LSTM/XGBoost/custom logic)
         │
         ▼
   C++ Engine (this folder)
   ┌─────────────────────────────┐
   │  Order Manager              │
   │  Risk Pre-checks (VaR)      │
   │  Lock-Free Order Book       │
   │  FIX/Alpaca Order Router    │
   │  Tick Replay Engine         │
   └─────────────────────────────┘
         │
         ▼
   Execution Venue (Alpaca / FIX broker)
```

---

## When Will It Be Built?

The C++ engine is planned for a future phase of development. Pre-requisites:
- The Python-based platform is fully stable in production
- Tick data from `backend/app/tasks/data_tasks.py` (`record_ticks`) has been accumulating for 30+ days across multiple symbols
- The team has scoped intraday / HFT strategy requirements

Until then, all execution goes through the Python backtesting engine (`backtesting/`) and the Alpaca paper trading API.

---

## How does this connect to the rest of the app?

- When built, the C++ engine will receive signals from `backend/app/services/orders/` and potentially from ML model predictions in `ml/`
- Its tick replay mode will use the `ticks` TimescaleDB hypertable populated by `backend/app/tasks/data_tasks.py`
- The Python bridge will allow `backend/app/api/v1/orders.py` to route orders either to Alpaca (current) or to the C++ engine (future)
