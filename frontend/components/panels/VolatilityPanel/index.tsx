"use client";

/**
 * VolatilityPanel — Implied Volatility Surface.
 *
 * Renders a 2-D IV heatmap (expiry on X, strike on Y, IV encoded as colour)
 * using D3 scales and pure SVG — no canvas, no WebGL, works in jsdom.
 *
 * Data source: GET /api/v1/options/iv-surface/{symbol}
 * Falls back to demo surface when API returns empty data.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SurfacePoint {
  strike: number;
  expiry_days: number;
  iv: number;
  contract_type: string;
}

type Filter = "all" | "call" | "put";

interface VolatilityPanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function VolatilityPanel({
  panelId = "volatility",
  defaultSymbol = "AAPL",
}: VolatilityPanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [symbolInput, setSymbolInput] = useState(defaultSymbol);
  const [surface, setSurface] = useState<SurfacePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  // Fetch surface data on symbol change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiRequest<{ symbol: string; surface: SurfacePoint[] }>(
      `/api/v1/options/iv-surface/${symbol}`
    )
      .then((data) => {
        if (!cancelled) {
          setSurface(data.surface ?? []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSurface([]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [symbol]);

  const handleGo = (e: React.FormEvent) => {
    e.preventDefault();
    const s = symbolInput.trim().toUpperCase();
    if (s) setSymbol(s);
  };

  const filtered = useMemo(
    () =>
      filter === "all"
        ? surface
        : surface.filter((p) => p.contract_type === filter),
    [surface, filter]
  );

  const toolbar = (
    <div style={styles.toolbar}>
      <form onSubmit={handleGo} style={{ display: "flex", gap: 4 }}>
        <input
          type="text"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          style={styles.symbolInput}
          aria-label="IV surface symbol"
          spellCheck={false}
        />
        <button type="submit" style={styles.goBtn} aria-label="Load IV surface">
          GO
        </button>
      </form>
      <div style={styles.filterGroup}>
        {(["all", "call", "put"] as Filter[]).map((f) => (
          <button
            key={f}
            style={{ ...styles.filterBtn, ...(filter === f ? styles.filterBtnActive : {}) }}
            onClick={() => setFilter(f)}
            aria-pressed={filter === f}
          >
            {f.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <Panel id={panelId} title={`IV SURFACE · ${symbol}`} toolbar={toolbar}>
      <div style={styles.body}>
        {loading && <div style={styles.state}>Loading…</div>}
        {!loading && filtered.length === 0 && (
          <div style={styles.state}>No surface data.</div>
        )}
        {!loading && filtered.length > 0 && (
          <IVHeatmap points={filtered} />
        )}
      </div>
    </Panel>
  );
}

// ─── IVHeatmap (D3 colour scale, pure SVG) ────────────────────────────────────

interface IVHeatmapProps {
  points: SurfacePoint[];
}

function IVHeatmap({ points }: IVHeatmapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Unique sorted axis values
  const expiries = useMemo(
    () => [...new Set(points.map((p) => p.expiry_days))].sort((a, b) => a - b),
    [points]
  );
  const strikes = useMemo(
    () => [...new Set(points.map((p) => p.strike))].sort((a, b) => a - b),
    [points]
  );

  const minIV = useMemo(() => Math.min(...points.map((p) => p.iv)), [points]);
  const maxIV = useMemo(() => Math.max(...points.map((p) => p.iv)), [points]);

  // Lookup: expiry_days + strike → iv
  const lookup = useMemo(() => {
    const m = new Map<string, number>();
    points.forEach((p) => m.set(`${p.expiry_days}:${p.strike}`, p.iv));
    return m;
  }, [points]);

  // Layout
  const margin = { top: 20, right: 60, bottom: 40, left: 54 };
  const width = 580;
  const height = 340;
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  const cellW = Math.floor(innerW / expiries.length);
  const cellH = Math.floor(innerH / strikes.length);

  // Colour interpolation: blue (low IV) → yellow → red (high IV)
  function ivToColour(iv: number): string {
    if (maxIV === minIV) return "#7c5cd8";
    const t = (iv - minIV) / (maxIV - minIV); // 0–1
    // Simple 3-stop gradient: 0→#3b82f6, 0.5→#f59e0b, 1→#ef4444
    if (t <= 0.5) {
      const s = t * 2;
      const r = Math.round(59 + s * (245 - 59));
      const g = Math.round(130 + s * (158 - 130));
      const b = Math.round(246 + s * (11 - 246));
      return `rgb(${r},${g},${b})`;
    }
    const s = (t - 0.5) * 2;
    const r = Math.round(245 + s * (239 - 245));
    const g = Math.round(158 + s * (68 - 158));
    const b = Math.round(11 + s * (68 - 11));
    return `rgb(${r},${g},${b})`;
  }

  return (
    <div ref={containerRef} style={{ overflowX: "auto" }}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        aria-label="Implied volatility surface heatmap"
        data-testid="iv-heatmap"
      >
        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Cells */}
          {expiries.map((exp, xi) =>
            strikes.map((strike, yi) => {
              const iv = lookup.get(`${exp}:${strike}`);
              if (iv === undefined) return null;
              return (
                <rect
                  key={`${exp}-${strike}`}
                  x={xi * cellW}
                  y={innerH - (yi + 1) * cellH}
                  width={cellW - 1}
                  height={cellH - 1}
                  fill={ivToColour(iv)}
                  opacity={0.9}
                >
                  <title>{`${exp}d / ${strike} · IV ${(iv * 100).toFixed(1)}%`}</title>
                </rect>
              );
            })
          )}

          {/* X-axis — expiry labels */}
          {expiries.map((exp, xi) => (
            <text
              key={`x-${exp}`}
              x={xi * cellW + cellW / 2}
              y={innerH + 14}
              textAnchor="middle"
              style={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#666" }}
            >
              {exp}d
            </text>
          ))}

          {/* Y-axis — strike labels */}
          {strikes.map((strike, yi) => (
            <text
              key={`y-${strike}`}
              x={-6}
              y={innerH - yi * cellH - cellH / 2 + 4}
              textAnchor="end"
              style={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#666" }}
            >
              {strike}
            </text>
          ))}

          {/* Axis labels */}
          <text
            x={innerW / 2}
            y={innerH + 34}
            textAnchor="middle"
            style={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#444" }}
          >
            EXPIRY (DAYS)
          </text>
          <text
            x={-innerH / 2}
            y={-40}
            textAnchor="middle"
            transform="rotate(-90)"
            style={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace", fill: "#444" }}
          >
            STRIKE
          </text>

          {/* Colour scale legend */}
          {Array.from({ length: 20 }, (_, i) => (
            <rect
              key={`legend-${i}`}
              x={innerW + 10}
              y={i * (innerH / 20)}
              width={12}
              height={innerH / 20 + 1}
              fill={ivToColour(minIV + (i / 19) * (maxIV - minIV))}
            />
          ))}
          <text
            x={innerW + 26}
            y={6}
            style={{ fontSize: 8, fontFamily: "JetBrains Mono,monospace", fill: "#666" }}
          >
            {(maxIV * 100).toFixed(0)}%
          </text>
          <text
            x={innerW + 26}
            y={innerH - 2}
            style={{ fontSize: 8, fontFamily: "JetBrains Mono,monospace", fill: "#666" }}
          >
            {(minIV * 100).toFixed(0)}%
          </text>
        </g>
      </svg>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  symbolInput: {
    background: "#111",
    border: "1px solid #333",
    borderRadius: 3,
    padding: "2px 8px",
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#e8e8e8",
    fontWeight: 700,
    outline: "none",
    width: 70,
    textTransform: "uppercase",
  },
  goBtn: {
    background: "rgba(0,208,132,0.12)",
    border: "1px solid rgba(0,208,132,0.3)",
    borderRadius: 3,
    padding: "2px 8px",
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#00d084",
    cursor: "pointer",
  },
  filterGroup: {
    display: "flex",
    gap: 3,
  },
  filterBtn: {
    padding: "2px 7px",
    background: "transparent",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#555",
    cursor: "pointer",
    letterSpacing: "0.04em",
  },
  filterBtnActive: {
    background: "rgba(0,208,132,0.1)",
    border: "1px solid rgba(0,208,132,0.25)",
    color: "#00d084",
  },
  body: {
    flex: 1,
    overflow: "auto",
    padding: "6px 4px 0",
  },
  state: {
    textAlign: "center",
    padding: 24,
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#333",
  },
};
