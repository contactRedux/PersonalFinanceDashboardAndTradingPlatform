# backtesting/ — Strategy Backtesting Engine

## What is this folder?

Backtesting answers the question: *"If I had used this trading strategy in the past, how much money would I have made or lost?"*

Think of it like a flight simulator. You can't crash a real plane to learn how to handle emergencies — but you can practice in a simulator first. Similarly, you can't go back in time to test a trading strategy with real money, but you can replay it against historical prices.

---

## Folder Structure

```
backtesting/
├── engine/        Core simulation logic (fast vectorized and realistic event-driven modes)
├── strategies/    Built-in trading strategies ready to test
├── optimization/  Tools to find the best strategy settings automatically
├── reporting/     Generate HTML and PDF reports of results
└── tests/         pytest tests for the engine and strategies
```

---

## Most Important Files

### `engine/`

**`vectorized.py`** — **`VectorizedEngine`**: The fast mode. Runs an entire backtest in one NumPy pass (NumPy is a Python library for fast array math). Applies the strategy's signals to the full price history at once. A 10-year daily backtest runs in milliseconds. Best for quick parameter sweeps.

**`event_driven.py`** — **`EventDrivenEngine`**: The realistic mode. Simulates trading bar-by-bar, processing four event types in order for each candle: `MarketEvent` (new price data) → `SignalEvent` (strategy decision) → `OrderEvent` (convert to order) → `FillEvent` (execute at next bar's open). This prevents **look-ahead bias** (accidentally using future data that wouldn't have been available at trade time).

**`base.py`** — **`BacktestResult`** and **`Trade`**: Data classes that hold a completed backtest's results. `BacktestResult.compute_metrics()` calculates all performance statistics from the equity curve and trade list.

### `strategies/`

All five built-in strategies implement a `generate_signals(data)` method that takes an OHLCV DataFrame (Open, High, Low, Close, Volume — the standard price data format) and returns a Series of +1 (go long/buy), -1 (go short/sell), or 0 (do nothing).

### `optimization/`

**`bayesian.py`** — **`BayesianOptimizer`**: Intelligently searches for the best parameters. Instead of trying all 10,000 combinations, it uses Optuna's TPE (Tree-structured Parzen Estimator — a Bayesian algorithm that learns from previous trials to focus on promising regions) to find near-optimal parameters in 50-100 trials. Typically 10-100x faster than grid search.

**`walk_forward.py`** — **`WalkForwardOptimizer`**: The gold standard for strategy validation. Splits historical data into sequential "in-sample" windows (for optimization) and "out-of-sample" windows (for testing). This prevents **overfitting** — tuning parameters so well to historical data that the strategy stops working on new data. Think of it as cross-validation for trading strategies.

**`grid_search.py`** — **`GridSearchOptimizer`**: Exhaustively tries every combination in a parameter grid. Simple but potentially slow for large grids.

**`monte_carlo.py`** — **`MonteCarlo`**: Takes the list of historical trades and randomly shuffles their order hundreds or thousands of times to see the distribution of possible outcomes. Answers "what's the worst-case scenario?" with statistical confidence.

### `reporting/`

**`html_report.py`** — **`generate_html_report(result, mc_result?)`**: Produces a single self-contained HTML file with: summary metric cards (total return, Sharpe ratio, max drawdown, etc.), an inline SVG equity curve chart, a Monte Carlo percentile table, and a full trade log.

**`pdf_report.py`** — **`generate_pdf_report(result)`**: Converts the HTML report to PDF using WeasyPrint. Used by the `/api/v1/backtest/{run_id}/report/pdf` endpoint.

---

## Performance Metrics Defined

| Metric | What it means in plain English |
|---|---|
| **Total Return %** | How much your account grew (or shrank) overall |
| **CAGR** | Compound Annual Growth Rate — the consistent annual return that would produce the same total result |
| **Sharpe Ratio** | Return per unit of risk. Above 1.0 is decent, above 2.0 is excellent |
| **Sortino Ratio** | Like Sharpe, but only penalizes downward volatility (most traders only care about downside risk) |
| **Max Drawdown %** | The worst peak-to-trough decline — "how much could you have lost at the worst point?" |
| **Calmar Ratio** | CAGR divided by max drawdown — how much return per unit of worst-case pain |
| **Win Rate %** | Percentage of trades that were profitable |
| **Profit Factor** | Total profit from winning trades ÷ total loss from losing trades. Above 1.5 is solid |

---

## How does this connect to the rest of the app?

- The `backend/app/api/v1/backtest.py` endpoint imports and calls `VectorizedEngine` and `EventDrivenEngine` directly to handle `POST /api/v1/backtest/run`
- The `BacktestPanel` in the frontend calls that endpoint and displays the equity curve and metrics
- Strategies and optimizers are also used by the visual `StrategyBuilderPanel` to validate saved node-graph configs
