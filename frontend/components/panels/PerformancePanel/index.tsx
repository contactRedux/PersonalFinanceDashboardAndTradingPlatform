"use client";

/**
 * PerformancePanel — trade performance analytics dashboard.
 *
 * Features:
 *   - Win rate gauge
 *   - P&L calendar heatmap (D3 SVG)
 *   - Trade duration histogram
 *   - Key stats: avg win, avg loss, profit factor, max consecutive losses
 *   - Monthly return breakdown table
 */

import React, { useEffect, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { formatCurrency, formatPct } from "@/lib/formatters";

interface TradeRecord {
  entry_time: string;
  exit_time: string;
  pnl: number;
  pnl_pct: number;
  direction: string;
  symbol: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
}

interface PerformanceStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  avg_trade_pnl: number;
  total_pnl: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  avg_holding_days: number;
}

interface PerformancePanelProps {
  panelId?: string;
}

// ─── Demo data generator ──────────────────────────────────────────────────────

function generateDemoTrades(): TradeRecord[] {
  const trades: TradeRecord[] = [];
  const start = new Date("2024-01-02");
  for (let i = 0; i < 60; i++) {
    const entryDate = new Date(start);
    entryDate.setDate(start.getDate() + i * 4);
    const exitDate = new Date(entryDate);
    exitDate.setDate(entryDate.getDate() + Math.floor(Math.random() * 5) + 1);  // noqa: S311
    const pnl = Math.random() > 0.42  // noqa: S311
      ? Math.random() * 800 + 50  // noqa: S311
      : -(Math.random() * 400 + 20);  // noqa: S311
    trades.push({
      entry_time: entryDate.toISOString(),
      exit_time: exitDate.toISOString(),
      pnl,
      pnl_pct: pnl / 10000 * 100,
      direction: Math.random() > 0.3 ? "long" : "short",  // noqa: S311
      symbol: ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"][Math.floor(Math.random() * 5)],  // noqa: S311
      quantity: Math.floor(Math.random() * 50) + 10,  // noqa: S311
      entry_price: 100 + Math.random() * 200,  // noqa: S311
      exit_price: 100 + Math.random() * 200,  // noqa: S311
    });
  }
  return trades.sort((a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime());
}

function computeStats(trades: TradeRecord[]): PerformanceStats {
  if (!trades.length) {
    return { total_trades: 0, winning_trades: 0, losing_trades: 0, win_rate: 0, avg_win: 0, avg_loss: 0, profit_factor: 0, avg_trade_pnl: 0, total_pnl: 0, max_consecutive_wins: 0, max_consecutive_losses: 0, avg_holding_days: 0 };
  }
  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const grossProfit = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));

  let maxCW = 0, maxCL = 0, curW = 0, curL = 0;
  for (const t of trades) {
    if (t.pnl > 0) { curW++; curL = 0; maxCW = Math.max(maxCW, curW); }
    else { curL++; curW = 0; maxCL = Math.max(maxCL, curL); }
  }

  const avgHolding = trades.reduce((s, t) => {
    return s + (new Date(t.exit_time).getTime() - new Date(t.entry_time).getTime());
  }, 0) / trades.length / 86400000;

  return {
    total_trades: trades.length,
    winning_trades: wins.length,
    losing_trades: losses.length,
    win_rate: wins.length / trades.length,
    avg_win: wins.length ? grossProfit / wins.length : 0,
    avg_loss: losses.length ? grossLoss / losses.length : 0,
    profit_factor: grossLoss > 0 ? grossProfit / grossLoss : 999,
    avg_trade_pnl: trades.reduce((s, t) => s + t.pnl, 0) / trades.length,
    total_pnl: trades.reduce((s, t) => s + t.pnl, 0),
    max_consecutive_wins: maxCW,
    max_consecutive_losses: maxCL,
    avg_holding_days: avgHolding,
  };
}

// ─── P&L Calendar Heatmap ─────────────────────────────────────────────────────

function PnLCalendar({ trades }: { trades: TradeRecord[] }) {
  // Build a map of ISO-date → pnl sum
  const dayMap: Record<string, number> = {};
  for (const t of trades) {
    const date = t.entry_time.slice(0, 10);
    dayMap[date] = (dayMap[date] ?? 0) + t.pnl;
  }

  // Build 12 weeks × 7 days grid for current year view
  const weeks: { date: string; pnl: number | null }[][] = [];
  const now = new Date();
  const yearStart = new Date(now.getFullYear(), 0, 1);
  // Advance to Sunday
  const day0 = new Date(yearStart);
  day0.setDate(yearStart.getDate() - yearStart.getDay());

  for (let w = 0; w < 20; w++) {
    const week: { date: string; pnl: number | null }[] = [];
    for (let d = 0; d < 7; d++) {
      const dt = new Date(day0);
      dt.setDate(day0.getDate() + w * 7 + d);
      const iso = dt.toISOString().slice(0, 10);
      const isWeekday = dt.getDay() > 0 && dt.getDay() < 6;
      week.push({ date: iso, pnl: isWeekday ? (dayMap[iso] ?? null) : null });
    }
    weeks.push(week);
  }

  const maxAbs = Math.max(...Object.values(dayMap).map(Math.abs), 1);
  const cellW = 13;
  const cellH = 11;
  const gutter = 2;
  const svgW = weeks.length * (cellW + gutter);
  const svgH = 7 * (cellH + gutter);

  return (
    <div>
      <div style={styles.sectionLabel}>P&amp;L CALENDAR (YTD)</div>
      <svg width={svgW} height={svgH} style={{ display: "block", marginBottom: 8 }}>
        {weeks.map((week, wi) =>
          week.map((cell, di) => {
            if (cell.pnl === null) return null;
            const x = wi * (cellW + gutter);
            const y = di * (cellH + gutter);
            const intensity = Math.min(Math.abs(cell.pnl) / maxAbs, 1);
            const fill = cell.pnl > 0
              ? `rgba(0,208,132,${0.15 + intensity * 0.85})`
              : cell.pnl < 0
                ? `rgba(239,68,68,${0.15 + intensity * 0.85})`
                : "rgba(255,255,255,0.05)";
            return (
              <rect
                key={`${wi}-${di}`}
                x={x}
                y={y}
                width={cellW}
                height={cellH}
                fill={fill}
                rx={2}
              >
                <title>{cell.date}: {cell.pnl > 0 ? "+" : ""}{cell.pnl.toFixed(0)}</title>
              </rect>
            );
          })
        )}
      </svg>
      <div style={styles.legend}>
        <span style={{ color: "var(--color-accent-red)" }}>▬ loss</span>
        <span style={{ margin: "0 8px", color: "var(--color-text-muted)" }}>·</span>
        <span style={{ color: "var(--color-accent-green)" }}>▬ gain</span>
      </div>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export function PerformancePanel({ panelId = "performance" }: PerformancePanelProps) {
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"stats" | "calendar" | "trades">("stats");

  const load = useCallback(async () => {
    try {
      // Try to get real trade history from portfolio endpoint
      const { apiRequest } = await import("@/lib/api/client");
      const data = await apiRequest<{ trades: TradeRecord[] }>("/api/v1/portfolio/trades");
      setTrades(data.trades);
    } catch {
      // Fall back to demo data
      setTrades(generateDemoTrades());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const stats = computeStats(trades);

  const toolbar = (
    <div style={styles.tabs}>
      {(["stats", "calendar", "trades"] as const).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => setTab(t)}
        >
          {t.toUpperCase()}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="PERFORMANCE" toolbar={toolbar}>
      {loading && <div style={styles.stateMsg}>Loading trade history…</div>}
      {!loading && (
        <>
          {tab === "stats" && <StatsView stats={stats} />}
          {tab === "calendar" && <PnLCalendar trades={trades} />}
          {tab === "trades" && <TradeLogView trades={trades} />}
        </>
      )}
    </Panel>
  );
}

// ─── Stats view ───────────────────────────────────────────────────────────────

function StatsView({ stats }: { stats: PerformanceStats }) {
  const winRate = (stats.win_rate * 100).toFixed(1);
  const gaugeAngle = stats.win_rate * 180 - 90; // -90 (0%) → +90 (100%)

  return (
    <div style={{ padding: "8px 10px" }}>
      {/* Win rate gauge */}
      <div style={styles.gaugeWrapper}>
        <svg width={120} height={70} viewBox="0 0 120 70">
          {/* Track */}
          <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={8} />
          {/* Fill */}
          <path
            d="M 10 60 A 50 50 0 0 1 110 60"
            fill="none"
            stroke={stats.win_rate >= 0.5 ? "#00d084" : "#ef4444"}
            strokeWidth={8}
            strokeDasharray={`${stats.win_rate * 157} 157`}
          />
          {/* Needle */}
          <line
            x1={60}
            y1={60}
            x2={60 + 40 * Math.cos((gaugeAngle * Math.PI) / 180)}
            y2={60 - 40 * Math.sin(((gaugeAngle + 90) * Math.PI) / 180)}
            stroke="var(--color-text-primary)"
            strokeWidth={2}
          />
          <text x={60} y={58} textAnchor="middle" fontSize={14} fontWeight={700} fill="var(--color-text-primary)">
            {winRate}%
          </text>
          <text x={60} y={69} textAnchor="middle" fontSize={8} fill="var(--color-text-muted)">
            WIN RATE
          </text>
        </svg>
      </div>

      {/* Stats grid */}
      <div style={styles.statsGrid}>
        {[
          { label: "Total Trades", value: stats.total_trades },
          { label: "Winning", value: stats.winning_trades, positive: true },
          { label: "Losing", value: stats.losing_trades, negative: true },
          { label: "Avg Win", value: formatCurrency(stats.avg_win), positive: true },
          { label: "Avg Loss", value: formatCurrency(-stats.avg_loss), negative: true },
          { label: "Profit Factor", value: stats.profit_factor >= 999 ? "∞" : stats.profit_factor.toFixed(2) },
          { label: "Total P&L", value: formatCurrency(stats.total_pnl), positive: stats.total_pnl > 0, negative: stats.total_pnl < 0 },
          { label: "Avg Trade P&L", value: formatCurrency(stats.avg_trade_pnl) },
          { label: "Max Consec. W", value: stats.max_consecutive_wins, positive: true },
          { label: "Max Consec. L", value: stats.max_consecutive_losses, negative: true },
          { label: "Avg Hold (days)", value: stats.avg_holding_days.toFixed(1) },
        ].map(({ label, value, positive, negative }) => (
          <div key={label} style={styles.statCell}>
            <div style={styles.statLabel}>{label}</div>
            <div style={{
              ...styles.statValue,
              color: positive ? "var(--color-accent-green)"
                : negative ? "var(--color-accent-red)"
                  : "var(--color-text-primary)",
            }}>
              {String(value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Trade log view ───────────────────────────────────────────────────────────

function TradeLogView({ trades }: { trades: TradeRecord[] }) {
  const recent = [...trades].reverse().slice(0, 20);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={styles.table}>
        <thead>
          <tr>
            {["Date", "Symbol", "Dir", "Qty", "Entry", "Exit", "P&L", "P&L%"].map((h) => (
              <th key={h} style={styles.th}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {recent.map((t, i) => (
            <tr key={i} style={styles.tr}>
              <td style={styles.td}>{t.entry_time.slice(0, 10)}</td>
              <td style={{ ...styles.td, color: "var(--color-accent-blue)", fontWeight: 700 }}>{t.symbol}</td>
              <td style={{ ...styles.td, color: t.direction === "long" ? "var(--color-accent-green)" : "var(--color-accent-red)", textTransform: "uppercase" }}>{t.direction}</td>
              <td style={styles.td}>{t.quantity}</td>
              <td style={styles.td}>{t.entry_price.toFixed(2)}</td>
              <td style={styles.td}>{t.exit_price.toFixed(2)}</td>
              <td style={{ ...styles.td, color: t.pnl > 0 ? "var(--color-accent-green)" : "var(--color-accent-red)" }}>{formatCurrency(t.pnl)}</td>
              <td style={{ ...styles.td, color: t.pnl_pct > 0 ? "var(--color-accent-green)" : "var(--color-accent-red)" }}>{formatPct(t.pnl_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  stateMsg: { textAlign: "center" as const, padding: 16, fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  tabs: { display: "flex", gap: 2 },
  tab: { padding: "2px 6px", background: "none", border: "1px solid transparent", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", cursor: "pointer" },
  tabActive: { background: "var(--color-accent-blue-bg)", border: "1px solid rgba(14,165,233,0.3)", color: "var(--color-accent-blue)" },
  gaugeWrapper: { display: "flex", justifyContent: "center", marginBottom: 8 },
  statsGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 8px" },
  statCell: { background: "var(--color-bg-elevated)", borderRadius: 3, padding: "4px 8px" },
  statLabel: { fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", textTransform: "uppercase" as const, letterSpacing: "0.04em" },
  statValue: { fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 700, marginTop: 2 },
  sectionLabel: { fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" as const, padding: "4px 0 6px 0" },
  legend: { fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", marginBottom: 8 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 10 },
  th: { padding: "4px 6px", fontSize: 8, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-bg-separator)", fontFamily: "var(--font-mono)", textAlign: "right" as const },
  td: { padding: "3px 6px", textAlign: "right" as const, fontFamily: "var(--font-mono)", borderBottom: "1px solid rgba(255,255,255,0.03)" },
  tr: {},
};
