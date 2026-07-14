# backtesting/optimization — Parameter Optimization

## What is this folder?

Every trading strategy has **parameters** — knobs you can turn to change its behavior. For example, an SMA crossover strategy has a "fast period" and a "slow period." Should the fast period be 10 days? 20 days? 50 days? The right settings can be the difference between a profitable strategy and a losing one.

This folder provides three ways to find the best settings automatically:

1. **Grid Search** — try every possible combination
2. **Bayesian Optimization** — be smart about which combinations to try
3. **Walk-Forward** — validate that good settings generalize to *new* data

There's also Monte Carlo simulation to stress-test results.

---

## Files

| File | Class | Method | Best for |
|---|---|---|---|
| `grid_search.py` | **`GridSearchOptimizer`** | Exhaustive | Small parameter spaces (< 100 combinations) |
| `bayesian.py` | **`BayesianOptimizer`** | Smart sampling | Larger spaces (10-300 trials) |
| `walk_forward.py` | **`WalkForwardOptimizer`** | Time-sequential | Validating a strategy before going live |
| `monte_carlo.py` | **`MonteCarlo`** | Simulation | Risk analysis of any completed backtest |

---

## Most Important Code

### `grid_search.py` — **`GridSearchOptimizer`**

**Analogy:** You're testing every combination on a menu. For 3 fast periods and 3 slow periods, that's 9 backtests to run. Results are ranked by your chosen metric (default: Sharpe ratio).

**`expand_grid(param_space)`** — A utility function that converts `{"fast": [10, 20], "slow": [40, 50, 60]}` into a flat list of all combinations: `[{"fast": 10, "slow": 40}, {"fast": 10, "slow": 50}, ...]`. Used internally by grid search and walk-forward.

**`GridSearchOptimizer.run(data, symbol, timeframe)`** → Returns a **`GridSearchResult`** with `best_params`, `best_value`, and `all_results` ranked from best to worst. The top 20 results are returned by the API.

---

### `bayesian.py` — **`BayesianOptimizer`**

**Analogy:** Instead of tasting every item on a huge menu, a knowledgeable sommelier suggests which wines to try based on what you've liked so far. Optuna (an open-source optimization framework) does the same — it learns from each trial to focus on promising parameter regions.

Uses **TPE** (Tree-structured Parzen Estimator — a Bayesian algorithm that models the probability that a parameter combination will beat the current best). Achieves equivalent results in 10-100x fewer trials than grid search.

**`BayesianOptimizer.run(data, symbol, timeframe)`** — Runs `n_trials` Optuna trials (default 50). Each trial picks parameters, runs a backtest, and reports the metric value back to Optuna so it can learn.

Returns a **`BayesianResult`** with `best_params`, `best_value`, and `trials` (the full trial history so you can see how the search converged).

**Parameter space format:** `{"fast": (5, 50, 1), "slow": (20, 200, 5)}` — each entry is `(low, high, step)`.

---

### `walk_forward.py` — **`WalkForwardOptimizer`**

**Analogy:** Before letting a student pilot fly passengers, you train them in a simulator, test them on a new scenario they haven't practiced, and only pass them if they perform well on the *new* scenario — not just the one they trained on. Walk-forward optimization does this for strategies.

1. Take the first `in_sample_bars` days (default 252 = one trading year) — optimize parameters on this window
2. Apply the best parameters to the *next* `out_of_sample_bars` days (default 63 = one quarter) — this is the "test"
3. Slide the window forward by the OOS size and repeat

The result is a combined equity curve built entirely from out-of-sample periods — a more honest picture of real-world performance.

**`WalkForwardOptimizer.run(data, strategy_cls)`** → Returns a **`WalkForwardResult`** containing:
- `folds` — per-window results with in-sample metrics and out-of-sample performance
- `combined_equity` — the full equity curve stitched from all OOS periods
- `avg_oos_sharpe` — average out-of-sample Sharpe ratio across all folds

---

### `monte_carlo.py` — **`MonteCarlo`**

Takes a `BacktestResult`'s trade list and runs `n_simulations` (default 500) random shuffles of those trades, rebuilding the equity curve each time. Outputs percentile statistics (5th, 25th, 50th, 75th, 95th) for final equity, max drawdown, and Sharpe ratio — plus the probability of overall profit.

**Use case:** You ran a strategy and got a 1.8 Sharpe ratio. But was that lucky sequencing? Monte Carlo tells you: "if trades arrived in a random order, 90% of simulations still show profit."

---

## How does this connect to the rest of the app?

- The `backend/app/api/v1/backtest.py` endpoint exposes all four methods via REST:
  - `POST /api/v1/backtest/optimize` → Bayesian
  - `POST /api/v1/backtest/grid-search` → Grid search
  - `POST /api/v1/backtest/wfo` → Walk-forward
  - The `run_monte_carlo: true` flag in `POST /api/v1/backtest/run` → Monte Carlo
- The `BacktestPanel` in the frontend displays these results interactively
- `WalkForwardOptimizer` uses `GridSearchOptimizer.expand_grid()` internally for its in-sample search step
