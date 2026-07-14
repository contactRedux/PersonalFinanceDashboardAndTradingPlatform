"use client";

/**
 * AIScorePanel — composite AI score gauge.
 *
 * Displays a 0–100 score derived from LSTM × 40 + XGBoost × 40 + FinBERT × 20.
 * Features:
 *   - SVG semi-circle gauge (red/amber/green zones)
 *   - Signal badge (BULLISH / NEUTRAL / BEARISH)
 *   - Sentiment bar (positive / neutral / negative proportional segments)
 *   - Top contributing factors (3 bullet points)
 *   - Loading / no-model states
 */

import React, { useState, useCallback, useEffect } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AIScoreResponse {
  ticker: string;
  score: number;
  signal: "bullish" | "neutral" | "bearish";
  reasoning: string[];
  components: {
    lstm_up: number;
    xgb_long: number;
    finbert_positive: number;
    finbert_negative: number;
    finbert_neutral: number;
  };
}

interface AIScorePanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

// ─── Gauge helpers ────────────────────────────────────────────────────────────

/** Converts polar degrees to SVG cartesian coordinates (origin at cx, cy). */
function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angleDeg: number
): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

/**
 * Build an SVG arc path.
 * The gauge goes from 180° (left) to 0° (right) — a top semi-circle.
 * angleDeg = 0 is the leftmost point (score=0), 180 is rightmost (score=100).
 */
function arcPath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
): string {
  const [sx, sy] = polarToCartesian(cx, cy, r, startAngle);
  const [ex, ey] = polarToCartesian(cx, cy, r, endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`;
}

/** Map a 0–100 score to a gauge colour. */
function scoreColor(score: number): string {
  if (score >= 67) return "#00d084";
  if (score >= 34) return "#f59e0b";
  return "#ef4444";
}

// ─── Component ────────────────────────────────────────────────────────────────

export function AIScorePanel({
  panelId = "ai-score",
  defaultSymbol = "AAPL",
}: AIScorePanelProps) {
  const [inputSymbol, setInputSymbol] = useState(defaultSymbol);
  const [activeSymbol, setActiveSymbol] = useState(defaultSymbol);
  const [data, setData] = useState<AIScoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [noModel, setNoModel] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScore = useCallback(async (sym: string) => {
    setLoading(true);
    setNoModel(false);
    setError(null);
    setData(null);
    try {
      const result = await apiRequest<AIScoreResponse>(
        `/ml/ai-score?ticker=${encodeURIComponent(sym.toUpperCase())}`
      );
      setData(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      // Treat "no model" conditions as the no-model state
      if (
        msg.toLowerCase().includes("no trained") ||
        msg.toLowerCase().includes("404")
      ) {
        setNoModel(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScore(activeSymbol);
  }, [activeSymbol, fetchScore]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const sym = inputSymbol.trim().toUpperCase();
      if (sym) {
        setActiveSymbol(sym);
      }
    },
    [inputSymbol]
  );

  // ── Gauge geometry ──────────────────────────────────────────────────────────
  const cx = 100;
  const cy = 100;
  const r = 75;

  // Gauge arc: 180° → 0° (left to right along the top half)
  // score 0 → start angle 180, score 100 → end angle 360 (= 0)
  const score = data?.score ?? 0;
  const gaugeStart = 180;
  const gaugeEnd = 180 + (score / 100) * 180;
  const color = scoreColor(score);

  // Signal colors
  const signalColor =
    data?.signal === "bullish"
      ? "#00d084"
      : data?.signal === "bearish"
      ? "#ef4444"
      : "#f59e0b";

  // FinBERT bar segments
  const fbPos = data?.components.finbert_positive ?? 0.33;
  const fbNeg = data?.components.finbert_negative ?? 0.33;
  const fbNeu = data?.components.finbert_neutral ?? 0.34;
  const fbTotal = fbPos + fbNeg + fbNeu || 1;
  const posW = (fbPos / fbTotal) * 100;
  const negW = (fbNeg / fbTotal) * 100;
  const neuW = (fbNeu / fbTotal) * 100;

  return (
    <Panel id={panelId} title="AI SCORE">
      <div style={styles.root}>
        {/* ── Symbol input ── */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value.toUpperCase())}
            style={styles.input}
            aria-label="AI score symbol"
            spellCheck={false}
            autoComplete="off"
          />
          <button type="submit" style={styles.goBtn} aria-label="Analyze symbol">
            GO
          </button>
        </form>

        {/* ── No-model state ── */}
        {noModel && !loading && (
          <div style={styles.noModel}>
            No models trained yet. Use POST /ml/lstm/train and POST
            /ml/xgboost/train to enable predictions.
          </div>
        )}

        {/* ── Error state ── */}
        {error && !loading && (
          <div style={styles.errorMsg}>{error}</div>
        )}

        {/* ── Main content (loading dimmed or normal) ── */}
        <div style={{ ...styles.content, opacity: loading ? 0.4 : 1 }}>
          {loading && (
            <div style={styles.analyzing}>Analyzing…</div>
          )}

          {/* Gauge SVG */}
          <div style={styles.gaugeWrap}>
            <svg width={200} height={110} viewBox="0 0 200 110" style={styles.svg}>
              {/* Background track */}
              <path
                d={arcPath(cx, cy, r, 180, 360)}
                fill="none"
                stroke="#1e1e1e"
                strokeWidth={12}
                strokeLinecap="round"
              />
              {/* Filled arc */}
              {score > 0 && (
                <path
                  d={arcPath(cx, cy, r, gaugeStart, gaugeEnd)}
                  fill="none"
                  stroke={color}
                  strokeWidth={12}
                  strokeLinecap="round"
                />
              )}
              {/* Score number */}
              <text
                x={cx}
                y={cy - 10}
                textAnchor="middle"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 28,
                  fontWeight: 700,
                  fill: color,
                }}
              >
                {data ? Math.round(score) : "—"}
              </text>
              {/* Label */}
              <text
                x={cx}
                y={cy + 14}
                textAnchor="middle"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  fill: "#555",
                  letterSpacing: "0.08em",
                }}
              >
                AI SCORE
              </text>
              {/* Scale endpoints */}
              <text x={18} y={108} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fill: "#333" }}>0</text>
              <text x={175} y={108} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fill: "#333" }}>100</text>
            </svg>
          </div>

          {/* Signal badge */}
          {data && (
            <div style={{ ...styles.badge, borderColor: signalColor, color: signalColor }}>
              {data.signal.toUpperCase()}
            </div>
          )}

          {/* Sentiment bar */}
          {data && (
            <div style={styles.section}>
              <div style={styles.sectionLabel}>SENTIMENT</div>
              <div style={styles.barTrack}>
                <div
                  style={{
                    ...styles.barSegment,
                    width: `${posW.toFixed(1)}%`,
                    background: "#00d084",
                  }}
                  title={`Positive: ${posW.toFixed(0)}%`}
                />
                <div
                  style={{
                    ...styles.barSegment,
                    width: `${neuW.toFixed(1)}%`,
                    background: "#444",
                  }}
                  title={`Neutral: ${neuW.toFixed(0)}%`}
                />
                <div
                  style={{
                    ...styles.barSegment,
                    width: `${negW.toFixed(1)}%`,
                    background: "#ef4444",
                  }}
                  title={`Negative: ${negW.toFixed(0)}%`}
                />
              </div>
              <div style={styles.barLabels}>
                <span style={{ color: "#00d084" }}>{posW.toFixed(0)}%</span>
                <span style={{ color: "#888" }}>{neuW.toFixed(0)}%</span>
                <span style={{ color: "#ef4444" }}>{negW.toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Top contributing factors */}
          {data && data.reasoning.length > 0 && (
            <div style={styles.section}>
              <div style={styles.sectionLabel}>CONTRIBUTING FACTORS</div>
              <ul style={styles.list}>
                {data.reasoning.slice(0, 3).map((r, i) => (
                  <li key={i} style={styles.listItem}>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Idle placeholder */}
          {!data && !loading && !noModel && !error && (
            <div style={styles.idle}>Enter a ticker above to analyze.</div>
          )}
        </div>
      </div>
    </Panel>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  root: {
    background: "#0a0a0a",
    color: "#e8e8e8",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    padding: "8px 10px",
    gap: 6,
    fontFamily: "'JetBrains Mono', monospace",
    boxSizing: "border-box",
  },
  form: {
    display: "flex",
    gap: 6,
    alignItems: "center",
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: "#111",
    border: "1px solid #2a2a2a",
    borderRadius: 3,
    padding: "3px 8px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e8e8e8",
    outline: "none",
    textTransform: "uppercase" as const,
  },
  goBtn: {
    padding: "3px 10px",
    background: "rgba(0,208,132,0.12)",
    border: "1px solid rgba(0,208,132,0.35)",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#00d084",
    cursor: "pointer",
    letterSpacing: "0.06em",
  },
  noModel: {
    background: "#111",
    border: "1px solid #2a2a2a",
    borderRadius: 4,
    padding: "10px 12px",
    fontSize: 10,
    color: "#555",
    lineHeight: 1.6,
    flexShrink: 0,
  },
  errorMsg: {
    padding: "6px 0",
    fontSize: 10,
    color: "#ef4444",
    flexShrink: 0,
  },
  content: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: 6,
    transition: "opacity 0.2s",
    minHeight: 0,
    overflow: "auto",
  },
  analyzing: {
    position: "absolute" as const,
    left: "50%",
    top: "50%",
    transform: "translate(-50%, -50%)",
    fontSize: 11,
    color: "#888",
    letterSpacing: "0.06em",
    pointerEvents: "none" as const,
  },
  gaugeWrap: {
    display: "flex",
    justifyContent: "center",
    flexShrink: 0,
  },
  svg: {
    overflow: "visible",
  },
  badge: {
    alignSelf: "center",
    padding: "3px 14px",
    border: "1px solid",
    borderRadius: 3,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.1em",
    flexShrink: 0,
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    flexShrink: 0,
  },
  sectionLabel: {
    fontSize: 8,
    color: "#444",
    letterSpacing: "0.1em",
  },
  barTrack: {
    display: "flex",
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    background: "#111",
  },
  barSegment: {
    height: "100%",
    transition: "width 0.4s",
    minWidth: 0,
  },
  barLabels: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
  },
  list: {
    margin: 0,
    paddingLeft: 14,
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  listItem: {
    fontSize: 10,
    color: "#aaa",
    lineHeight: 1.5,
  },
  idle: {
    textAlign: "center",
    padding: 16,
    fontSize: 11,
    color: "#333",
  },
};
