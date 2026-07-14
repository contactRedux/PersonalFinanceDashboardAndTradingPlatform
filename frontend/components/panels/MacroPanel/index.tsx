"use client";

/**
 * MacroPanel — macro economic overview with live FRED data.
 *
 * Features:
 *  - Key indicator tiles (Fed Funds, CPI, GDP, Unemployment, VIX, DXY)
 *  - US Treasury yield curve rendered as an SVG line chart
 *  - Yield curve inversion warning banner
 *  - VIX regime badge (Low / Normal / Elevated / High / Extreme Fear)
 */

import React, { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Panel } from "@/components/layout/Panel";
import {
  getMacroIndicators,
  getYieldCurve,
  getVix,
  type MacroSnapshot,
  type YieldPoint,
} from "@/lib/api/screener";

interface MacroPanelProps { panelId?: string; }

const VIX_REGIME_COLOR: Record<string, string> = {
  low_volatility:  "var(--color-accent-green)",
  normal:          "var(--color-accent-blue)",
  elevated:        "var(--color-accent-amber)",
  high_volatility: "var(--color-accent-red)",
  extreme_fear:    "#ff00ff",
};

export function MacroPanel({ panelId = "macro" }: MacroPanelProps) {
  const [snapshot, setSnapshot] = useState<MacroSnapshot | null>(null);
  const [curve, setCurve] = useState<YieldPoint[]>([]);
  const [vix, setVix] = useState<{ value: number; regime: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [inverted, setInverted] = useState(false);

  const load = useCallback(async () => {
    try {
      const [snapRes, curveRes, vixRes] = await Promise.all([
        getMacroIndicators(),
        getYieldCurve(),
        getVix(),
      ]);
      setSnapshot(snapRes);
      setCurve(curveRes.curve);
      setInverted(curveRes.inverted);
      setVix(vixRes);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 5 * 60_000);
    return () => clearInterval(interval);
  }, [load]);

  const INDICATOR_KEYS = ["fed_funds_rate", "cpi", "gdp", "unemployment", "yield_spread", "breakeven_inf", "dxy"];

  return (
    <Panel id={panelId} title="Macro Overview">
      {loading && <div style={styles.stateMsg}>Loading macro data…</div>}

      {!loading && (
        <>
          {/* Inversion warning */}
          {inverted && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={styles.inversionBanner}
            >
              ⚠ Yield curve inverted (10Y &lt; 2Y) — historical recession signal
            </motion.div>
          )}

          {/* VIX badge */}
          {vix && (
            <div style={styles.vixRow}>
              <span style={styles.label}>VIX</span>
              <span style={{ ...styles.vixValue, color: VIX_REGIME_COLOR[vix.regime] ?? "var(--color-text-primary)" }}>
                {vix.value.toFixed(2)}
              </span>
              <span style={{ ...styles.regimeBadge, borderColor: VIX_REGIME_COLOR[vix.regime] ?? "transparent", color: VIX_REGIME_COLOR[vix.regime] }}>
                {vix.regime.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>
          )}

          {/* Indicator tiles */}
          <div style={styles.tileGrid}>
            {snapshot && INDICATOR_KEYS.map((key) => {
              const ind = snapshot[key] as { value: number | null; label: string; unit: string } | undefined;
              if (!ind) return null;
              const isNegative = typeof ind.value === "number" && ind.value < 0;
              return (
                <div key={key} style={styles.tile}>
                  <div style={styles.tileLabel}>{ind.label}</div>
                  <div style={{ ...styles.tileValue, color: isNegative ? "var(--color-accent-red)" : "var(--color-text-primary)" }}>
                    {ind.value != null ? ind.value.toFixed(2) : "—"}
                    <span style={styles.tileUnit}> {ind.unit}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Yield curve chart */}
          {curve.length > 0 && <YieldCurveChart points={curve} inverted={inverted} />}
        </>
      )}
    </Panel>
  );
}

// ─── SVG yield curve chart ─────────────────────────────────────────────────────
function YieldCurveChart({ points, inverted }: { points: YieldPoint[]; inverted: boolean }) {
  const W = 320, H = 80, PAD = 24;
  const yields = points.map((p) => p.yield);
  const minY = Math.min(...yields) - 0.2;
  const maxY = Math.max(...yields) + 0.2;
  const n = points.length;

  const toX = (i: number) => PAD + ((W - PAD * 2) / (n - 1)) * i;
  const toY = (v: number) => H - PAD - ((v - minY) / (maxY - minY)) * (H - PAD * 2);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(p.yield).toFixed(1)}`)
    .join(" ");

  const lineColor = inverted ? "var(--color-accent-red)" : "var(--color-accent-blue)";

  return (
    <div style={{ padding: "4px 8px 8px" }}>
      <div style={styles.chartTitle}>US TREASURY YIELD CURVE</div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible" }}>
        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((t) => {
          const y = PAD + (H - PAD * 2) * t;
          return <line key={t} x1={PAD} x2={W - PAD} y1={y} y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth={0.5} />;
        })}

        {/* Yield curve line */}
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} />

        {/* Data points */}
        {points.map((p, i) => (
          <g key={p.maturity}>
            <circle cx={toX(i)} cy={toY(p.yield)} r={2} fill={lineColor} />
            {(i === 0 || i === n - 1 || i === Math.floor(n / 2)) && (
              <>
                <text x={toX(i)} y={H - 4} textAnchor="middle" fontSize={7} fill="rgba(255,255,255,0.4)">{p.maturity}</text>
                <text x={toX(i)} y={toY(p.yield) - 5} textAnchor="middle" fontSize={7} fill={lineColor}>{p.yield.toFixed(2)}%</text>
              </>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg: { textAlign: "center" as const, padding: "16px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  inversionBanner: { padding: "4px 10px", background: "rgba(239,68,68,0.1)", borderBottom: "1px solid rgba(239,68,68,0.2)", fontSize: 10, color: "var(--color-accent-red)", fontFamily: "var(--font-mono)" },
  vixRow: { display: "flex", alignItems: "center", gap: 8, padding: "5px 10px", borderBottom: "1px solid var(--color-bg-separator)" },
  label: { fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em" },
  vixValue: { fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 700 },
  regimeBadge: { padding: "1px 5px", border: "1px solid", borderRadius: 3, fontSize: 8, fontFamily: "var(--font-mono)", letterSpacing: "0.06em" },
  tileGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, padding: "4px", borderBottom: "1px solid var(--color-bg-separator)" },
  tile: { padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 2 },
  tileLabel: { fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.05em", marginBottom: 2 },
  tileValue: { fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700 },
  tileUnit: { fontSize: 8, color: "var(--color-text-muted)", fontWeight: 400 },
  chartTitle: { fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", letterSpacing: "0.08em", marginBottom: 4 },
};
