"use client";

/**
 * HeatMapPanel — S&P 500 sector treemap with % change color coding.
 *
 * Renders a pure SVG treemap partitioned by sector.
 * Each stock cell is colored by its 1-day % change:
 *   dark red  → -3%+  |  red → -1%  |  neutral → 0  |  green → +1%  |  bright green → +3%+
 *
 * Uses squarified treemap layout algorithm.
 */

import React, { useEffect, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { getSectorMap, type SectorData } from "@/lib/api/screener";

interface HeatMapPanelProps { panelId?: string; }

interface TreemapCell {
  symbol: string;
  name: string;
  sector: string;
  change: number;
  weight: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

function changeToBg(change: number): string {
  if (change <= -3)  return "#7f1d1d";
  if (change <= -1)  return "#dc2626";
  if (change < -0.1) return "#991b1b";
  if (change < 0.1)  return "#374151";
  if (change < 1)    return "#166534";
  if (change < 3)    return "#16a34a";
  return "#15803d";
}

function changeToText(change: number): string {
  return Math.abs(change) > 1.5 ? "#ffffff" : "rgba(255,255,255,0.9)";
}

/** Simplified row-based treemap layout */
function buildTreemap(
  data: { symbol: string; name: string; sector: string; change: number; weight: number }[],
  x: number, y: number, w: number, h: number
): TreemapCell[] {
  if (data.length === 0) return [];
  const total = data.reduce((s, d) => s + d.weight, 0);

  const cells: TreemapCell[] = [];
  let remainX = x, remainY = y, remainW = w, remainH = h;
  let remaining = [...data];

  while (remaining.length > 0) {
    const isWide = remainW >= remainH;
    const dim = isWide ? remainH : remainW;

    // Find how many items fit in the next row/column
    let rowSum = 0;
    let bestWorst = Infinity;
    let rowCount = 0;

    for (let i = 0; i < remaining.length; i++) {
      rowSum += remaining[i].weight;
      const rowDim = (rowSum / total) * (isWide ? remainW : remainH);
      let worst = 0;
      for (let j = 0; j <= i; j++) {
        const area = (remaining[j].weight / total) * (isWide ? remainW : remainH) * dim / (rowSum / total) * (isWide ? remainW : remainH);
        const cellDim = area / dim;
        const ratio = Math.max(dim / cellDim, cellDim / dim);
        if (ratio > worst) worst = ratio;
      }
      if (worst < bestWorst) {
        bestWorst = worst;
        rowCount = i + 1;
      } else {
        break;
      }
      void rowDim;
    }
    rowCount = Math.max(1, rowCount);

    const rowItems = remaining.slice(0, rowCount);
    const rowWeightSum = rowItems.reduce((s, d) => s + d.weight, 0);
    const rowFrac = rowWeightSum / total;
    const rowDim = rowFrac * (isWide ? remainW : remainH);

    let cursor = isWide ? remainY : remainX;
    for (const item of rowItems) {
      const frac = item.weight / rowWeightSum;
      const cellDim = frac * dim;
      cells.push({
        ...item,
        x: isWide ? remainX : cursor,
        y: isWide ? cursor : remainY,
        w: isWide ? rowDim : cellDim,
        h: isWide ? cellDim : rowDim,
      });
      cursor += cellDim;
    }

    if (isWide) {
      remainX += rowDim;
      remainW -= rowDim;
    } else {
      remainY += rowDim;
      remainH -= rowDim;
    }
    remaining = remaining.slice(rowCount);
  }

  return cells;
}

export function HeatMapPanel({ panelId = "heatmap" }: HeatMapPanelProps) {
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ text: string; x: number; y: number } | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getSectorMap();
      setSectors(res.sectors);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 60_000);
    return () => clearInterval(interval);
  }, [load]);

  const W = 500, H = 280;
  const PAD = 1;

  // Build flat data list sorted by market cap
  const flatData = sectors.flatMap((s) =>
    s.stocks.map((st) => ({
      symbol: st.symbol,
      name: st.name,
      sector: s.sector,
      change: st.change_pct_1d,
      weight: Math.max(st.market_cap / 1000, 1),
    }))
  ).sort((a, b) => b.weight - a.weight);

  const cells = buildTreemap(flatData, PAD, PAD, W - PAD * 2, H - PAD * 2);

  return (
    <Panel id={panelId} title="Sector Heat Map">
      {loading && <div style={styles.stateMsg}>Loading heat map…</div>}

      {!loading && (
        <div style={{ position: "relative", userSelect: "none" }}>
          {/* Sector avg change legend */}
          <div style={styles.legendRow}>
            {sectors.map((s) => (
              <div key={s.sector} style={styles.legendItem}>
                <span style={{ ...styles.legendDot, background: changeToBg(s.avg_change_pct) }} />
                <span style={styles.legendLabel}>{s.sector}</span>
                <span style={{ ...styles.legendChange, color: s.avg_change_pct >= 0 ? "var(--color-accent-green)" : "var(--color-accent-red)" }}>
                  {s.avg_change_pct >= 0 ? "+" : ""}{s.avg_change_pct.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>

          <svg
            width="100%"
            viewBox={`0 0 ${W} ${H}`}
            style={{ display: "block", cursor: "crosshair" }}
            onMouseLeave={() => setTooltip(null)}
          >
            {cells.map((cell) => (
              <g key={cell.symbol}>
                <rect
                  x={cell.x}
                  y={cell.y}
                  width={Math.max(0, cell.w - 1)}
                  height={Math.max(0, cell.h - 1)}
                  fill={changeToBg(cell.change)}
                  rx={1}
                  onMouseEnter={(e) => {
                    const svgRect = (e.currentTarget.closest("svg") as SVGSVGElement)?.getBoundingClientRect();
                    setTooltip({
                      text: `${cell.symbol}: ${cell.change >= 0 ? "+" : ""}${cell.change.toFixed(2)}%`,
                      x: e.clientX - (svgRect?.left ?? 0),
                      y: e.clientY - (svgRect?.top ?? 0),
                    });
                  }}
                />
                {cell.w > 28 && cell.h > 16 && (
                  <text
                    x={cell.x + cell.w / 2}
                    y={cell.y + cell.h / 2 + (cell.h > 28 ? -4 : 3)}
                    textAnchor="middle"
                    fontSize={Math.min(10, cell.w / 5)}
                    fontFamily="var(--font-mono)"
                    fontWeight={700}
                    fill={changeToText(cell.change)}
                    style={{ pointerEvents: "none" }}
                  >
                    {cell.symbol}
                  </text>
                )}
                {cell.w > 28 && cell.h > 28 && (
                  <text
                    x={cell.x + cell.w / 2}
                    y={cell.y + cell.h / 2 + 8}
                    textAnchor="middle"
                    fontSize={Math.min(8, cell.w / 7)}
                    fontFamily="var(--font-mono)"
                    fill="rgba(255,255,255,0.7)"
                    style={{ pointerEvents: "none" }}
                  >
                    {cell.change >= 0 ? "+" : ""}{cell.change.toFixed(2)}%
                  </text>
                )}
              </g>
            ))}
          </svg>

          {/* Tooltip */}
          {tooltip && (
            <div
              style={{
                ...styles.tooltip,
                left: tooltip.x + 8,
                top: tooltip.y - 24,
              }}
            >
              {tooltip.text}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  stateMsg: { textAlign: "center" as const, padding: "16px", fontSize: 11, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  legendRow: { display: "flex", flexWrap: "wrap" as const, gap: 4, padding: "4px 8px", borderBottom: "1px solid var(--color-bg-separator)" },
  legendItem: { display: "flex", alignItems: "center", gap: 3 },
  legendDot: { width: 7, height: 7, borderRadius: 2, display: "inline-block", flexShrink: 0 },
  legendLabel: { fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" },
  legendChange: { fontSize: 8, fontFamily: "var(--font-mono)", fontWeight: 700 },
  tooltip: { position: "absolute" as const, background: "var(--color-bg-elevated)", border: "1px solid var(--color-bg-border)", borderRadius: 3, padding: "2px 6px", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-primary)", pointerEvents: "none", zIndex: 10, whiteSpace: "nowrap" as const },
};
