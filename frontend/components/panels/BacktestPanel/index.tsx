"use client";

/**
 * BacktestPanel — run and visualise backtests against the QuantNexus engine.
 *
 * Features:
 *   - Form: symbol, date range, strategy, params, engine (vectorized / event_driven)
 *   - Equity curve rendered as a lightweight-charts LineSeries
 *   - Metrics grid (total return, CAGR, Sharpe, max drawdown, win rate, profit factor)
 *   - Trade log table (symbol, direction, entry/exit price, P&L)
 *   - Monte Carlo toggle
 *
 * Chart rendering happens in a plain useEffect with createChart — no dependency on
 * ChartCanvas to avoid coupling. The canvas mock in vitest covers the unit test path.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface TradeRecord {
  entry_time: string;
  exit_time: string;
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
}

interface BacktestResult {
  symbol: string;
  timeframe: string;
  start: string;
  end: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  equity_curve: number[];
  trades: TradeRecord[];
  monte_carlo: {
    n_simulations: number;
    p05_final_equity: number;
    median_final_equity: number;
    p95_final_equity: number;
    p05_max_drawdown: number;
    median_max_drawdown: number;
    prob_profit: number;
  } | null;
}

type TabId = "chart" | "metrics" | "trades";

const STRATEGIES = [
  { label: "SMA Cross", value: "sma_cross" },
  { label: "RSI Mean Reversion", value: "rsi_mean_reversion" },
  { label: "MACD Cross", value: "macd_cross" },
  { label: "Bollinger Band", value: "bollinger_band" },
  { label: "VWAP Reversion", value: "vwap_reversion" },
];

interface BacktestPanelProps {
  panelId?: string;
}

export function BacktestPanel({ panelId = "backtest" }: BacktestPanelProps) {
  // ── Form state ──────────────────────────────────────────────────────────────
  const [symbol, setSymbol] = useState("AAPL");
  const [start, setStart] = useState("2022-01-01");
  const [end, setEnd] = useState("2024-01-01");
  const [strategy, setStrategy] = useState("sma_cross");
  const [paramFast, setParamFast] = useState(20);
  const [paramSlow, setParamSlow] = useState(50);
  const [engine, setEngine] = useState<"vectorized" | "event_driven">("vectorized");
  const [runMC, setRunMC] = useState(false);

  // ── Result state ────────────────────────────────────────────────────────────
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeTab, setActiveTab] = useState<TabId>("chart");

  // ── Chart canvas ────────────────────────────────────────────────────────────
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<unknown>(null);

  const handleRun = useCallback(async () => {
    setStatus("running");
    setResult(null);
    setErrorMsg("");
    try {
      const data = await apiRequest<BacktestResult>("/api/v1/backtest/run", {
        method: "POST",
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          timeframe: "1d",
          start,
          end,
          strategy,
          params: strategy === "sma_cross" ? { fast: paramFast, slow: paramSlow } : {},
          engine,
          run_monte_carlo: runMC,
          mc_simulations: 500,
        }),
      });
      setResult(data);
      setStatus("done");
      setActiveTab("chart");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Backtest failed");
      setStatus("error");
    }
  }, [symbol, start, end, strategy, paramFast, paramSlow, engine, runMC]);

  // Render equity curve when result arrives and chart tab is active
  useEffect(() => {
    if (!result || activeTab !== "chart" || !chartContainerRef.current) return;

    let chart: import("lightweight-charts").IChartApi | undefined;
    (async () => {
      try {
        const { createChart, LineSeries } = await import("lightweight-charts");
        if (!chartContainerRef.current) return;
        chart = createChart(chartContainerRef.current, {
          autoSize: true,
          layout: {
            background: { color: "#0a0a0a" },
            textColor: "#8a8a8a",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
          },
          grid: {
            vertLines: { color: "#1a1a1a", style: 1 },
            horzLines: { color: "#1a1a1a", style: 1 },
          },
          rightPriceScale: { borderColor: "#222" },
          timeScale: { borderColor: "#222", timeVisible: false },
        });
        chartInstanceRef.current = chart;

        const series = chart.addSeries(LineSeries, {
          color: "#00d084",
          lineWidth: 2,
          priceLineVisible: false,
        });

        series.setData(
          result.equity_curve.map((value, i) => ({
            time: i as unknown as import("lightweight-charts").Time,
            value,
          }))
        );
        chart.timeScale().fitContent();
      } catch {
        // canvas unavailable (e.g., in jsdom) — graceful no-op
      }
    })();

    return () => {
      try {
        chart?.remove(); // chart is captured in closure
      } catch {
        // ignore cleanup errors in test env
      }
      chartInstanceRef.current = null;
    };
  }, [result, activeTab]);

  const toolbar = (
    <div style={styles.tabs}>
      {(["chart", "metrics", "trades"] as TabId[]).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(activeTab === t ? styles.tabActive : {}) }}
          onClick={() => setActiveTab(t)}
          aria-pressed={activeTab === t}
        >
          {t.toUpperCase()}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="BACKTEST" toolbar={toolbar}>
      {/* ── Form ──────────────────────────────────────────────────────────── */}
      <div style={styles.form}>
        <div style={styles.formRow}>
          <label style={styles.label}>
            Symbol
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              style={styles.input}
              aria-label="Backtest symbol"
              spellCheck={false}
            />
          </label>
          <label style={styles.label}>
            Start
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              style={styles.input}
              aria-label="Backtest start date"
            />
          </label>
          <label style={styles.label}>
            End
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              style={styles.input}
              aria-label="Backtest end date"
            />
          </label>
        </div>

        <div style={styles.formRow}>
          <label style={styles.label}>
            Strategy
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              style={styles.select}
              aria-label="Backtest strategy"
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          {strategy === "sma_cross" && (
            <>
              <label style={styles.label}>
                Fast
                <input
                  type="number"
                  value={paramFast}
                  min={2}
                  max={200}
                  onChange={(e) => setParamFast(Number(e.target.value))}
                  style={{ ...styles.input, width: 60 }}
                  aria-label="SMA fast period"
                />
              </label>
              <label style={styles.label}>
                Slow
                <input
                  type="number"
                  value={paramSlow}
                  min={3}
                  max={500}
                  onChange={(e) => setParamSlow(Number(e.target.value))}
                  style={{ ...styles.input, width: 60 }}
                  aria-label="SMA slow period"
                />
              </label>
            </>
          )}

          <label style={styles.label}>
            Engine
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as "vectorized" | "event_driven")}
              style={styles.select}
              aria-label="Backtest engine"
            >
              <option value="vectorized">Vectorized</option>
              <option value="event_driven">Event-Driven</option>
            </select>
          </label>

          <label style={{ ...styles.label, flexDirection: "row", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={runMC}
              onChange={(e) => setRunMC(e.target.checked)}
              aria-label="Run Monte Carlo"
            />
            <span style={styles.labelText}>Monte Carlo</span>
          </label>
        </div>

        <button
          style={{
            ...styles.runBtn,
            opacity: status === "running" ? 0.5 : 1,
            cursor: status === "running" ? "not-allowed" : "pointer",
          }}
          onClick={handleRun}
          disabled={status === "running"}
          aria-label="Run backtest"
        >
          {status === "running" ? "RUNNING…" : "▶  RUN BACKTEST"}
        </button>
      </div>

      {/* ── Status messages ────────────────────────────────────────────── */}
      {status === "error" && <div style={styles.error}>{errorMsg}</div>}

      {/* ── Result views ───────────────────────────────────────────────── */}
      {status === "done" && result && (
        <div style={styles.results}>
          {/* Equity curve tab */}
          {activeTab === "chart" && (
            <div style={styles.chartWrap}>
              <div ref={chartContainerRef} style={styles.chartCanvas} data-testid="backtest-chart" />
            </div>
          )}

          {/* Metrics tab */}
          {activeTab === "metrics" && (
            <div style={styles.metricsGrid}>
              <MetricTile label="Total Return" value={`${result.total_return_pct.toFixed(2)}%`} />
              <MetricTile label="CAGR" value={`${result.cagr_pct.toFixed(2)}%`} />
              <MetricTile label="Sharpe" value={result.sharpe_ratio.toFixed(3)} />
              <MetricTile label="Sortino" value={result.sortino_ratio.toFixed(3)} />
              <MetricTile label="Calmar" value={result.calmar_ratio.toFixed(3)} />
              <MetricTile label="Max Drawdown" value={`${result.max_drawdown_pct.toFixed(2)}%`} />
              <MetricTile label="Win Rate" value={`${result.win_rate.toFixed(1)}%`} />
              <MetricTile label="Profit Factor" value={result.profit_factor.toFixed(2)} />
              <MetricTile label="Total Trades" value={String(result.total_trades)} />
              <MetricTile label="Wins" value={String(result.winning_trades)} />
              <MetricTile label="Losses" value={String(result.losing_trades)} />
              <MetricTile
                label="Final Equity"
                value={`$${result.final_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              />
              {result.monte_carlo && (
                <>
                  <MetricTile
                    label="MC Median Equity"
                    value={`$${result.monte_carlo.median_final_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  />
                  <MetricTile
                    label="MC P5 Equity"
                    value={`$${result.monte_carlo.p05_final_equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                  />
                  <MetricTile
                    label="MC Prob Profit"
                    value={`${(result.monte_carlo.prob_profit * 100).toFixed(1)}%`}
                  />
                </>
              )}
            </div>
          )}

          {/* Trade log tab */}
          {activeTab === "trades" && (
            <div style={styles.tradeLogWrap}>
              {result.trades.length === 0 ? (
                <div style={styles.emptyMsg}>No trades generated.</div>
              ) : (
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Symbol</th>
                      <th style={styles.th}>Dir</th>
                      <th style={styles.th}>Entry</th>
                      <th style={styles.th}>Exit</th>
                      <th style={styles.th}>P&L</th>
                      <th style={styles.th}>P&L%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i} style={styles.row}>
                        <td style={styles.td}>{t.symbol}</td>
                        <td
                          style={{
                            ...styles.td,
                            color: t.direction === "long" ? "#00d084" : "#ef4444",
                          }}
                        >
                          {t.direction.toUpperCase()}
                        </td>
                        <td style={styles.td}>{t.entry_price.toFixed(2)}</td>
                        <td style={styles.td}>{t.exit_price.toFixed(2)}</td>
                        <td
                          style={{
                            ...styles.td,
                            color: t.pnl >= 0 ? "#00d084" : "#ef4444",
                          }}
                        >
                          {t.pnl >= 0 ? "+" : ""}
                          {t.pnl.toFixed(2)}
                        </td>
                        <td
                          style={{
                            ...styles.td,
                            color: t.pnl_pct >= 0 ? "#00d084" : "#ef4444",
                          }}
                        >
                          {t.pnl_pct >= 0 ? "+" : ""}
                          {t.pnl_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* Idle placeholder */}
      {status === "idle" && (
        <div style={styles.idle}>Configure and run a backtest above.</div>
      )}
    </Panel>
  );
}

// ─── MetricTile helper ────────────────────────────────────────────────────────
function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={metricStyles.tile}>
      <span style={metricStyles.label}>{label}</span>
      <span style={metricStyles.value}>{value}</span>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  form: {
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    borderBottom: "1px solid #1a1a1a",
    flexShrink: 0,
  },
  formRow: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
    alignItems: "flex-end",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#666",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  },
  labelText: {
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#888",
    letterSpacing: "0.06em",
  },
  input: {
    background: "#111",
    border: "1px solid #2a2a2a",
    borderRadius: 3,
    padding: "2px 6px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e0e0e0",
    outline: "none",
    width: 100,
  },
  select: {
    background: "#111",
    border: "1px solid #2a2a2a",
    borderRadius: 3,
    padding: "2px 6px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e0e0e0",
    outline: "none",
  },
  runBtn: {
    alignSelf: "flex-start",
    padding: "4px 16px",
    background: "rgba(0,208,132,0.15)",
    border: "1px solid rgba(0,208,132,0.4)",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#00d084",
    letterSpacing: "0.08em",
    cursor: "pointer",
  },
  tabs: {
    display: "flex",
    gap: 2,
  },
  tab: {
    padding: "1px 8px",
    background: "transparent",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#555",
    cursor: "pointer",
    letterSpacing: "0.06em",
  },
  tabActive: {
    background: "rgba(0,208,132,0.1)",
    border: "1px solid rgba(0,208,132,0.25)",
    color: "#00d084",
  },
  error: {
    padding: "8px 10px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#ef4444",
  },
  results: {
    flex: 1,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  chartWrap: {
    flex: 1,
    minHeight: 0,
  },
  chartCanvas: {
    width: "100%",
    height: "100%",
    minHeight: 220,
    background: "#0a0a0a",
  },
  metricsGrid: {
    padding: "10px",
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 6,
    overflow: "auto",
  },
  tradeLogWrap: {
    flex: 1,
    overflow: "auto",
    padding: "6px 10px",
  },
  emptyMsg: {
    textAlign: "center",
    padding: 16,
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#444",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
  },
  th: {
    textAlign: "right",
    padding: "3px 6px",
    color: "#444",
    fontSize: 9,
    letterSpacing: "0.06em",
    borderBottom: "1px solid #1a1a1a",
  },
  td: {
    textAlign: "right",
    padding: "3px 6px",
    color: "#c0c0c0",
    borderBottom: "1px solid #111",
  },
  row: {},
  idle: {
    textAlign: "center",
    padding: 24,
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#333",
  },
};

const metricStyles: Record<string, React.CSSProperties> = {
  tile: {
    background: "#0d0d0d",
    border: "1px solid #1a1a1a",
    borderRadius: 4,
    padding: "6px 8px",
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  label: {
    fontSize: 8,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#444",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  value: {
    fontSize: 13,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e0e0e0",
    fontWeight: 700,
  },
};
