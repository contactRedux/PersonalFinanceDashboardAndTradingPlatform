"use client";

/**
 * RiskPanel — portfolio risk metrics and position sizing calculator.
 *
 * Displays:
 *  - VaR (95%), CVaR (95%)
 *  - Sharpe, Sortino, Calmar ratios
 *  - Beta, Alpha vs benchmark
 *  - Max Drawdown + duration
 *  - Kelly Criterion position sizing calculator
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import { getRiskMetrics, type RiskMetricsResponse } from "@/lib/api/portfolio";
import { formatPct } from "@/lib/formatters";

interface RiskPanelProps {
  panelId?: string;
}

type Tab = "metrics" | "sizing";

export function RiskPanel({ panelId = "risk" }: RiskPanelProps) {
  const [tab, setTab] = useState<Tab>("metrics");
  const [metrics, setMetrics] = useState<RiskMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    try {
      const data = await getRiskMetrics();
      setMetrics(data);
      setError(null);
    } catch {
      setError("Failed to load risk metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMetrics();
    const interval = setInterval(() => void loadMetrics(), 60_000);
    return () => clearInterval(interval);
  }, [loadMetrics]);

  const toolbar = (
    <div style={{ display: "flex", gap: 2 }}>
      {(["metrics", "sizing"] as Tab[]).map((t) => (
        <button
          key={t}
          style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
          onClick={() => setTab(t)}
        >
          {t === "metrics" ? "RISK METRICS" : "POSITION SIZING"}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="Risk Management" toolbar={toolbar}>
      {loading && <div style={styles.stateMsg}>Loading risk metrics…</div>}
      {error && (
        <div style={{ ...styles.stateMsg, color: "var(--color-accent-red)" }}>
          {error}
        </div>
      )}

      {!loading && !error && metrics && (
        <motion.div
          key={tab}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.12 }}
        >
          {tab === "metrics" ? (
            <RiskMetricsView metrics={metrics} />
          ) : (
            <PositionSizingCalculator equity={100_000} />
          )}
        </motion.div>
      )}
    </Panel>
  );
}

// ─── Risk metrics display ─────────────────────────────────────────────────────
function RiskMetricsView({ metrics }: { metrics: RiskMetricsResponse }) {
  // Color ratios — positive ratios are good
  const ratioColor = (v: number, goodAbove = 1) =>
    v >= goodAbove
      ? "var(--color-accent-green)"
      : v >= 0
        ? "var(--color-accent-amber)"
        : "var(--color-accent-red)";

  const sections: {
    title: string;
    rows: { label: string; value: string; color?: string; tooltip?: string }[];
  }[] = [
    {
      title: "Value at Risk",
      rows: [
        {
          label: "VaR (95%, 1-day)",
          value: formatPct(metrics.var_95 * 100),
          color: "var(--color-accent-amber)",
          tooltip: "Historical simulation: worst 5% of daily returns",
        },
        {
          label: "CVaR / ES (95%)",
          value: formatPct(metrics.cvar_95 * 100),
          color: "var(--color-accent-red)",
          tooltip: "Expected Shortfall: average loss beyond VaR threshold",
        },
      ],
    },
    {
      title: "Return Ratios",
      rows: [
        {
          label: "Sharpe Ratio",
          value: metrics.sharpe_ratio.toFixed(3),
          color: ratioColor(metrics.sharpe_ratio, 1),
          tooltip: "Annualized (return − risk-free) / std deviation",
        },
        {
          label: "Sortino Ratio",
          value: metrics.sortino_ratio.toFixed(3),
          color: ratioColor(metrics.sortino_ratio, 1),
          tooltip: "Uses only downside deviation",
        },
        {
          label: "Calmar Ratio",
          value: metrics.calmar_ratio.toFixed(3),
          color: ratioColor(metrics.calmar_ratio, 0.5),
          tooltip: "CAGR / Max Drawdown",
        },
      ],
    },
    {
      title: "Drawdown",
      rows: [
        {
          label: "Max Drawdown",
          value: formatPct(metrics.max_drawdown * 100),
          color:
            metrics.max_drawdown > 0.2
              ? "var(--color-accent-red)"
              : metrics.max_drawdown > 0.1
                ? "var(--color-accent-amber)"
                : "var(--color-accent-green)",
        },
        {
          label: "MDD Duration",
          value: `${metrics.max_drawdown_duration_days} days`,
          color: "var(--color-text-secondary)",
        },
      ],
    },
    {
      title: "Market Exposure",
      rows: [
        {
          label: "Beta (vs SPY)",
          value: metrics.beta.toFixed(3),
          color:
            Math.abs(metrics.beta - 1) < 0.2
              ? "var(--color-accent-amber)"
              : metrics.beta < 1
                ? "var(--color-accent-green)"
                : "var(--color-accent-red)",
          tooltip: "Portfolio sensitivity to market moves",
        },
        {
          label: "Alpha (annualized)",
          value: formatPct(metrics.alpha * 100),
          color: metrics.alpha >= 0 ? "var(--color-accent-green)" : "var(--color-accent-red)",
          tooltip: "Excess return vs benchmark after risk adjustment",
        },
      ],
    },
  ];

  return (
    <div>
      {sections.map((section) => (
        <div key={section.title}>
          <div style={styles.sectionHeader}>{section.title.toUpperCase()}</div>
          {section.rows.map(({ label, value, color, tooltip }) => (
            <div key={label} style={styles.metricRow} title={tooltip}>
              <span style={styles.metricLabel}>{label}</span>
              <span style={{ ...styles.metricValue, color: color ?? "var(--color-text-primary)" }}>
                {value}
              </span>
            </div>
          ))}
        </div>
      ))}

      {metrics.note && (
        <div style={styles.note}>{metrics.note}</div>
      )}
    </div>
  );
}

// ─── Position sizing calculator ───────────────────────────────────────────────
function PositionSizingCalculator({ equity }: { equity: number }) {
  const [winRate, setWinRate] = useState(0.55);
  const [avgWin, setAvgWin] = useState(2.0);
  const [avgLoss, setAvgLoss] = useState(1.0);
  const [riskPct, setRiskPct] = useState(1.0);

  // Kelly Criterion
  const b = avgLoss > 0 ? avgWin / avgLoss : 0;
  const kelly = b > 0 ? ((b * winRate - (1 - winRate)) / b) : 0;
  const halfKelly = Math.max(0, Math.min(kelly * 0.5, 0.25));

  // Fixed fractional
  const fixedFractional = riskPct / 100;

  const kellyUSD = halfKelly * equity;
  const fixedUSD = fixedFractional * equity;

  const stats: { label: string; value: string; color?: string }[] = [
    {
      label: "Win Rate",
      value: formatPct(winRate * 100),
    },
    {
      label: "Avg Win / Avg Loss",
      value: `${avgWin.toFixed(2)}R`,
    },
    {
      label: "Expectancy",
      value: ((winRate * avgWin) - ((1 - winRate) * avgLoss)).toFixed(3) + "R",
      color:
        (winRate * avgWin) - ((1 - winRate) * avgLoss) > 0
          ? "var(--color-accent-green)"
          : "var(--color-accent-red)",
    },
    {
      label: "Kelly Fraction",
      value: formatPct(kelly * 100),
      color: kelly > 0 ? "var(--color-accent-green)" : "var(--color-accent-red)",
    },
    {
      label: "Half-Kelly Size",
      value: `${formatPct(halfKelly * 100)} ($${kellyUSD.toFixed(0)})`,
      color: "var(--color-accent-blue)",
    },
    {
      label: "Fixed Frac. Size",
      value: `${formatPct(fixedFractional * 100)} ($${fixedUSD.toFixed(0)})`,
      color: "var(--color-accent-amber)",
    },
  ];

  return (
    <div style={{ padding: "4px 0" }}>
      <div style={styles.sectionHeader}>INPUT PARAMETERS</div>

      <div style={styles.calcSection}>
        <SliderField
          label="Win Rate"
          value={winRate}
          min={0.1}
          max={0.9}
          step={0.01}
          display={`${(winRate * 100).toFixed(0)}%`}
          onChange={setWinRate}
        />
        <SliderField
          label="Avg Win (R)"
          value={avgWin}
          min={0.1}
          max={10}
          step={0.1}
          display={`${avgWin.toFixed(1)}R`}
          onChange={setAvgWin}
        />
        <SliderField
          label="Avg Loss (R)"
          value={avgLoss}
          min={0.1}
          max={5}
          step={0.1}
          display={`${avgLoss.toFixed(1)}R`}
          onChange={setAvgLoss}
        />
        <SliderField
          label="Fixed Risk %"
          value={riskPct}
          min={0.1}
          max={5}
          step={0.1}
          display={`${riskPct.toFixed(1)}%`}
          onChange={setRiskPct}
        />
      </div>

      <div style={styles.sectionHeader}>RESULTS</div>
      {stats.map(({ label, value, color }) => (
        <div key={label} style={styles.metricRow}>
          <span style={styles.metricLabel}>{label}</span>
          <span style={{ ...styles.metricValue, color: color ?? "var(--color-text-primary)" }}>
            {value}
          </span>
        </div>
      ))}

      <div style={styles.note}>
        Half-Kelly sizing recommended. Never exceed 25% capital per trade.
        Past win rates do not guarantee future performance.
      </div>
    </div>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (v: number) => void;
}) {
  return (
    <div style={styles.sliderRow}>
      <span style={styles.sliderLabel}>{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={styles.slider}
        aria-label={label}
      />
      <span style={styles.sliderValue}>{display}</span>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  stateMsg: {
    textAlign: "center" as const,
    padding: "16px",
    fontSize: 11,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  tab: {
    padding: "2px 6px",
    background: "none",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 8,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
    letterSpacing: "0.05em",
    whiteSpace: "nowrap" as const,
  },
  tabActive: {
    background: "var(--color-accent-amber-bg)",
    border: "1px solid rgba(245,158,11,0.3)",
    color: "var(--color-accent-amber)",
  },
  sectionHeader: {
    padding: "4px 10px 2px",
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: "0.1em",
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
    background: "var(--color-bg-elevated)",
    borderTop: "1px solid var(--color-bg-separator)",
    borderBottom: "1px solid var(--color-bg-separator)",
  },
  metricRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "3px 10px",
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  metricLabel: {
    fontSize: 10,
    color: "var(--color-text-secondary)",
    fontFamily: "var(--font-sans)",
  },
  metricValue: {
    fontSize: 11,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    textAlign: "right" as const,
  },
  note: {
    padding: "6px 10px",
    fontSize: 9,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
    borderTop: "1px solid var(--color-bg-separator)",
    lineHeight: 1.5,
  },
  calcSection: {
    padding: "4px 0",
  },
  sliderRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "3px 10px",
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  sliderLabel: {
    fontSize: 10,
    color: "var(--color-text-secondary)",
    fontFamily: "var(--font-sans)",
    minWidth: 80,
  },
  slider: {
    flex: 1,
    accentColor: "var(--color-accent-amber)",
    height: 3,
  },
  sliderValue: {
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    minWidth: 44,
    textAlign: "right" as const,
  },
};
