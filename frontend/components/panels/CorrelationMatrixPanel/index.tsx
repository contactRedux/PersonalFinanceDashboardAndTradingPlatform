"use client";

/**
 * CorrelationMatrixPanel — pairwise asset correlation heatmap.
 *
 * Renders a symmetric NxN color grid where:
 *   +1.0 → bright green (perfect positive correlation)
 *    0.0 → neutral gray
 *   -1.0 → bright red (perfect negative correlation)
 *
 * Symbol list is editable — defaults to 8 major assets.
 */

import React, { useEffect, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { getCorrelations } from "@/lib/api/screener";

interface CorrelationMatrixPanelProps { panelId?: string; }

const DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "SPY"];

function corrToColor(v: number): string {
  if (v >= 0.9)  return "#064e3b";
  if (v >= 0.7)  return "#065f46";
  if (v >= 0.5)  return "#166534";
  if (v >= 0.3)  return "#14532d";
  if (v >= 0.1)  return "#374151";
  if (v >= -0.1) return "#1f2937";
  if (v >= -0.3) return "#7f1d1d";
  if (v >= -0.5) return "#991b1b";
  if (v >= -0.7) return "#b91c1c";
  return "#dc2626";
}

export function CorrelationMatrixPanel({ panelId = "correlation" }: CorrelationMatrixPanelProps) {
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS);
  const [matrix, setMatrix] = useState<number[][]>([]);
  const [loading, setLoading] = useState(true);
  const [inputVal, setInputVal] = useState(DEFAULT_SYMBOLS.join(","));
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);

  const load = useCallback(async (syms: string[]) => {
    setLoading(true);
    try {
      const res = await getCorrelations(syms);
      setSymbols(res.symbols);
      setMatrix(res.matrix);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(symbols); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleApply = () => {
    const syms = inputVal.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 12);
    if (syms.length >= 2) void load(syms);
  };

  const n = symbols.length;
  const CELL = Math.min(32, Math.floor(280 / Math.max(n, 1)));

  const toolbar = (
    <div style={{ display: "flex", gap: 3 }}>
      <input
        type="text"
        value={inputVal}
        onChange={(e) => setInputVal(e.target.value.toUpperCase())}
        style={styles.input}
        aria-label="Symbols for correlation"
        spellCheck={false}
        placeholder="AAPL,MSFT,SPY…"
      />
      <button style={styles.applyBtn} onClick={handleApply}>GO</button>
    </div>
  );

  return (
    <Panel id={panelId} title="Correlation Matrix" toolbar={toolbar}>
      {loading && <div style={styles.stateMsg}>Computing correlations…</div>}

      {!loading && matrix.length > 0 && (
        <div style={{ padding: "6px 8px", overflowX: "auto", position: "relative" }}>
          <div style={{ display: "inline-block" }}>
            {/* Column headers */}
            <div style={{ display: "flex", marginLeft: CELL + 2 }}>
              {symbols.map((sym) => (
                <div key={sym} style={{ ...styles.header, width: CELL, height: 20 }}>
                  {sym.slice(0, 4)}
                </div>
              ))}
            </div>

            {/* Matrix rows */}
            {symbols.map((rowSym, i) => (
              <div key={rowSym} style={{ display: "flex", alignItems: "center" }}>
                {/* Row label */}
                <div style={{ ...styles.header, width: CELL, height: CELL, textAlign: "right" as const, paddingRight: 4 }}>
                  {rowSym.slice(0, 4)}
                </div>
                {symbols.map((colSym, j) => {
                  const val = matrix[i]?.[j] ?? 0;
                  const isDiag = i === j;
                  return (
                    <div
                      key={colSym}
                      style={{
                        width: CELL,
                        height: CELL,
                        background: isDiag ? "var(--color-accent-blue-bg)" : corrToColor(val),
                        border: "1px solid rgba(0,0,0,0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "default",
                        position: "relative" as const,
                      }}
                      onMouseEnter={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        const parentRect = e.currentTarget.closest("[data-matrix]")?.getBoundingClientRect();
                        setTooltip({
                          text: `${rowSym} / ${colSym}: ${val.toFixed(3)}`,
                          x: rect.left - (parentRect?.left ?? 0) + CELL / 2,
                          y: rect.top - (parentRect?.top ?? 0) - 6,
                        });
                      }}
                      onMouseLeave={() => setTooltip(null)}
                    >
                      {CELL >= 24 && (
                        <span style={{
                          fontSize: 7,
                          fontFamily: "var(--font-mono)",
                          color: isDiag ? "var(--color-accent-blue)" : "rgba(255,255,255,0.75)",
                          fontWeight: isDiag ? 700 : 400,
                        }}>
                          {isDiag ? "1.00" : val.toFixed(2)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          {/* Tooltip */}
          {tooltip && (
            <div style={{ ...styles.tooltip, left: tooltip.x, top: tooltip.y }} data-matrix>
              {tooltip.text}
            </div>
          )}

          {/* Legend */}
          <div style={styles.legendRow}>
            {[-1, -0.5, 0, 0.5, 1].map((v) => (
              <div key={v} style={styles.legendItem}>
                <span style={{ display: "inline-block", width: 12, height: 8, background: corrToColor(v), borderRadius: 1 }} />
                <span style={styles.legendLabel}>{v >= 0 ? "+" : ""}{v.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg: { textAlign: "center" as const, padding: "16px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  input: { width: 160, background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, color: "var(--color-text-primary)", fontSize: 9, fontFamily: "var(--font-mono)", padding: "2px 5px", outline: "none" },
  applyBtn: { padding: "2px 6px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-accent-blue)", cursor: "pointer" },
  header: { fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", display: "flex", alignItems: "center", justifyContent: "center" },
  tooltip: { position: "absolute" as const, background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, padding: "2px 6px", fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-primary)", pointerEvents: "none", zIndex: 10, whiteSpace: "nowrap" as const, transform: "translate(-50%, -100%)" },
  legendRow: { display: "flex", gap: 8, marginTop: 6, alignItems: "center" },
  legendItem: { display: "flex", gap: 3, alignItems: "center" },
  legendLabel: { fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" },
};
