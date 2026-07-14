"""
HTML performance report generator.

Produces a self-contained HTML report from a ``BacktestResult``, optionally
including Monte Carlo simulation results.

Usage::

    from backtesting.reporting.html_report import generate_html_report

    html = generate_html_report(result, mc_result=mc_result)
    with open("report.html", "w") as f:
        f.write(html)
"""

from __future__ import annotations

from backtesting.engine.base import BacktestResult
from backtesting.optimization.monte_carlo import MonteCarloResult


_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantNexus Backtest Report — {symbol}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px;
         line-height: 1.6; color: #1f2328; background: #fff; padding: 32px 16px; margin: 0; }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; border-bottom: 1px solid #e5e7eb; padding-bottom: 5px;
        margin: 28px 0 12px; }}
  .subtitle {{ color: #57606a; font-size: 13px; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }}
  th {{ background: #f7f8fa; border: 1px solid #e5e7eb; padding: 6px 10px;
        text-align: left; font-weight: 700; }}
  td {{ border: 1px solid #e5e7eb; padding: 6px 10px; }}
  tr:nth-child(even) td {{ background: #fafbfc; }}
  .pos {{ color: #166534; font-weight: 600; }}
  .neg {{ color: #991b1b; font-weight: 600; }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
                  margin-bottom: 16px; }}
  .metric-card {{ background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 6px;
                  padding: 12px 14px; }}
  .metric-label {{ font-size: 11px; color: #57606a; margin-bottom: 2px; }}
  .metric-value {{ font-size: 20px; font-weight: 700; }}
  pre {{ background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 5px;
         padding: 12px; font-size: 12px; overflow-x: auto; }}
  footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb;
             text-align: center; font-size: 12px; color: #57606a; }}
  svg {{ overflow: visible; }}
</style>
</head>
<body>
<div class="wrap">
<h1>QuantNexus Backtest Report — {symbol}</h1>
<p class="subtitle">{timeframe} &nbsp;·&nbsp; {start} → {end}
&nbsp;·&nbsp; Initial capital: ${initial_capital:,.0f}</p>

<h2>Summary Metrics</h2>
<div class="metric-grid">
  <div class="metric-card">
    <div class="metric-label">Total Return</div>
    <div class="metric-value {ret_cls}">{total_return_pct:+.2f}%</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">CAGR</div>
    <div class="metric-value {cagr_cls}">{cagr:+.2f}%</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Sharpe Ratio</div>
    <div class="metric-value {sharpe_cls}">{sharpe_ratio:.2f}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Sortino Ratio</div>
    <div class="metric-value">{sortino_ratio:.2f}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Max Drawdown</div>
    <div class="metric-value neg">{max_drawdown_pct:.2f}%</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Calmar Ratio</div>
    <div class="metric-value">{calmar_ratio:.2f}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Win Rate</div>
    <div class="metric-value">{win_rate:.1f}%</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Profit Factor</div>
    <div class="metric-value">{profit_factor:.2f}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Total Trades</div>
    <div class="metric-value">{total_trades}</div>
  </div>
</div>

<h2>Equity Curve</h2>
{equity_svg}

{mc_section}

<h2>Trade Log</h2>
{trade_table}

<footer>Made with IBM Bob · QuantNexus Backtesting Engine</footer>
</div>
</body>
</html>
"""


def _build_equity_svg(equity_curve: list[float], width: int = 860, height: int = 200) -> str:
    """Render equity curve as inline SVG polyline."""
    if len(equity_curve) < 2:
        return "<p>Not enough data to render equity curve.</p>"
    mn = min(equity_curve)
    mx = max(equity_curve)
    span = mx - mn if mx != mn else 1.0
    pad = 10
    pts = []
    n = len(equity_curve)
    for i, v in enumerate(equity_curve):
        x = pad + (i / (n - 1)) * (width - 2 * pad)
        y = pad + (1 - (v - mn) / span) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    points = " ".join(pts)
    color = "#16a34a" if equity_curve[-1] >= equity_curve[0] else "#dc2626"
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="border:1px solid #e5e7eb;border-radius:5px;background:#f7f8fa">'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f"</svg>"
    )


def _build_trade_table(result: BacktestResult) -> str:
    if not result.trades:
        return "<p>No trades executed.</p>"
    rows = []
    for t in result.trades:
        cls = "pos" if t.pnl > 0 else "neg"
        rows.append(
            f"<tr>"
            f"<td>{t.entry_time.date()}</td>"
            f"<td>{t.exit_time.date()}</td>"
            f"<td>{t.direction}</td>"
            f"<td>{t.entry_price:.2f}</td>"
            f"<td>{t.exit_price:.2f}</td>"
            f"<td>{t.quantity:.2f}</td>"
            f"<td class='{cls}'>{t.pnl:+,.2f}</td>"
            f"<td class='{cls}'>{t.pnl_pct:+.2f}%</td>"
            f"</tr>"
        )
    table = (
        "<table><thead><tr>"
        "<th>Entry</th><th>Exit</th><th>Dir</th>"
        "<th>Entry Price</th><th>Exit Price</th><th>Qty</th>"
        "<th>P&amp;L $</th><th>P&amp;L %</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return table


def _build_mc_section(mc: MonteCarloResult) -> str:
    return f"""<h2>Monte Carlo ({mc.n_simulations:,} simulations)</h2>
<table>
<thead><tr><th>Percentile</th><th>Final Equity</th><th>Max Drawdown</th><th>Sharpe</th></tr></thead>
<tbody>
<tr><td>5th</td><td>${mc.p05_final_equity:,.0f}</td><td>{mc.p05_max_drawdown:.2f}%</td><td>{mc.p05_sharpe:.2f}</td></tr>
<tr><td>25th</td><td>${mc.p25_final_equity:,.0f}</td><td>—</td><td>—</td></tr>
<tr><td>50th (median)</td><td>${mc.median_final_equity:,.0f}</td><td>{mc.median_max_drawdown:.2f}%</td><td>{mc.median_sharpe:.2f}</td></tr>
<tr><td>75th</td><td>${mc.p75_final_equity:,.0f}</td><td>—</td><td>—</td></tr>
<tr><td>95th</td><td>${mc.p95_final_equity:,.0f}</td><td>{mc.p95_max_drawdown:.2f}%</td><td>{mc.p95_sharpe:.2f}</td></tr>
</tbody>
</table>
<p>Probability of profit: <strong>{mc.prob_profit * 100:.1f}%</strong></p>"""


def generate_html_report(
    result: BacktestResult,
    mc_result: MonteCarloResult | None = None,
) -> str:
    """Generate a self-contained HTML backtest report."""
    result.compute_metrics()

    ret_cls = "pos" if result.total_return_pct >= 0 else "neg"
    cagr_cls = "pos" if result.cagr >= 0 else "neg"
    sharpe_cls = "pos" if result.sharpe_ratio >= 1.0 else ("neg" if result.sharpe_ratio < 0 else "")

    return _TEMPLATE.format(
        symbol=result.symbol,
        timeframe=result.timeframe,
        start=result.start.date(),
        end=result.end.date(),
        initial_capital=result.initial_capital,
        total_return_pct=result.total_return_pct,
        ret_cls=ret_cls,
        cagr=result.cagr * 100.0,
        cagr_cls=cagr_cls,
        sharpe_ratio=result.sharpe_ratio,
        sharpe_cls=sharpe_cls,
        sortino_ratio=result.sortino_ratio,
        max_drawdown_pct=result.max_drawdown_pct,
        calmar_ratio=result.calmar_ratio,
        win_rate=result.win_rate * 100.0,
        profit_factor=result.profit_factor if result.profit_factor != float("inf") else 999.0,
        total_trades=result.total_trades,
        equity_svg=_build_equity_svg(result.equity_curve),
        trade_table=_build_trade_table(result),
        mc_section=_build_mc_section(mc_result) if mc_result else "",
    )
