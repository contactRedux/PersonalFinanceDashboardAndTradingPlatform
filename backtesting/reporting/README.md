# backtesting/reporting — Performance Reports

## What is this folder?

After a backtest runs, this folder's code turns the raw numbers (equity curve, trade list, metrics) into polished, human-readable reports — both as a web page (HTML) and as a downloadable document (PDF).

Think of it like the printout a financial advisor hands you after reviewing your portfolio — a clear summary of performance with charts, tables, and commentary.

---

## Files

| File | What it produces |
|---|---|
| `html_report.py` | A self-contained `.html` file with charts, metric cards, and trade log |
| `pdf_report.py` | A downloadable `.pdf` (converts the HTML using WeasyPrint) |

---

## `html_report.py` — `generate_html_report(result, mc_result?)`

The main reporting function. It takes a **`BacktestResult`** object (and optionally a **`MonteCarloResult`**) and returns a complete HTML string with no external dependencies — everything (CSS styles, the chart, the tables) is embedded inline so you can open the file on any computer without an internet connection.

### What's in the report?

**Summary Metric Cards** — 9 key numbers displayed in a 3×3 grid:
- Total Return % (green if positive, red if negative)
- CAGR (Compound Annual Growth Rate — the steady annual return that would produce the same total result)
- Sharpe Ratio (>1 = good, >2 = excellent)
- Sortino Ratio (like Sharpe but only counts downside risk)
- Max Drawdown % (worst peak-to-valley loss — always shown in red)
- Calmar Ratio (CAGR ÷ max drawdown)
- Win Rate %
- Profit Factor (total gains ÷ total losses)
- Total Trades

**Equity Curve** — An inline SVG (Scalable Vector Graphics — a resolution-independent chart format) line chart showing account value over time. The line is green if the strategy ended in profit, red if it ended at a loss.

**`_build_equity_svg(equity_curve)`** — Internal function that converts a list of numbers to an SVG polyline. It normalizes the values to fit within the chart area, plots each point, and colors the line green/red based on overall profitability.

**Monte Carlo Table** — If `mc_result` is provided, shows a 5-row table of percentile outcomes (5th through 95th) for final equity, max drawdown, and Sharpe ratio. Also shows the "probability of profit" from the simulations.

**Trade Log Table** — A table of every individual trade with: entry date, exit date, direction (long/short), entry price, exit price, quantity, P&L in dollars, and P&L as a percentage.

---

## `pdf_report.py` — `generate_pdf_report(result)`

Calls `generate_html_report()` to get the HTML, then passes it through **WeasyPrint** (a Python library that converts HTML/CSS to PDF, like printing a web page to PDF but programmatically) to produce bytes that can be sent as a file download.

Used by the `GET /api/v1/backtest/{run_id}/report/pdf` endpoint. The `run_id` references a `BacktestResult` kept in an in-memory cache for 100 most recent runs.

---

## Example Output Metrics (from a real report)

```
Symbol: AAPL  |  1d bars  |  2020-01-01 → 2024-01-01  |  $100,000 initial capital

Total Return: +148.32%     CAGR:  +25.1%       Sharpe: 1.84
Sortino:         2.31      Max DD: -18.6%       Calmar: 1.35
Win Rate:       58.3%      Profit Factor: 2.12  Trades:   84
```

---

## How does this connect to the rest of the app?

- `generate_html_report()` is called by the backtesting API endpoint to embed report data in the API response
- `generate_pdf_report()` powers the PDF download button in the `BacktestPanel`
- Both functions depend on `BacktestResult` from `backtesting/engine/base.py` — the same object produced by `VectorizedEngine.run()` and `EventDrivenEngine.run()`
- `MonteCarloResult` from `backtesting/optimization/monte_carlo.py` is optionally passed in for simulation percentile tables
