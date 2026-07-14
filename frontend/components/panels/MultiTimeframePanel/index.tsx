"use client";

/**
 * MultiTimeframePanel — shows the same symbol in 4 timeframes side-by-side.
 *
 * Default grid: 1m | 5m | 1h | 1d
 * Uses lightweight-charts v5 CandlestickSeries per pane.
 * Each pane fetches independently from the market data API.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { getBars, type BarData } from "@/lib/api/market";

type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d";

const DEFAULT_TIMEFRAMES: Timeframe[] = ["1m", "5m", "1h", "1d"];
const TF_LABELS: Record<Timeframe, string> = {
  "1m": "1M", "5m": "5M", "15m": "15M", "1h": "1H", "4h": "4H", "1d": "1D",
};
const TF_LIMIT: Record<Timeframe, number> = {
  "1m": 200, "5m": 200, "15m": 150, "1h": 150, "4h": 100, "1d": 200,
};

interface MultiTimeframePanelProps {
  panelId?: string;
  defaultSymbol?: string;
}

// ─── Single-pane chart ────────────────────────────────────────────────────────

interface PaneProps {
  symbol: string;
  timeframe: Timeframe;
}

function ChartPane({ symbol, timeframe }: PaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;

    const container = containerRef.current;
    container.innerHTML = "";

    let chart: { remove: () => void } | null = null;

    (async () => {
      try {
        const lc = await import("lightweight-charts");

        const newChart = lc.createChart(container, {
          width: container.clientWidth || 200,
          height: 160,
          layout: {
            background: { color: "transparent" },
            textColor: "rgba(255,255,255,0.4)",
            fontSize: 9,
          },
          grid: {
            vertLines: { color: "rgba(255,255,255,0.04)" },
            horzLines: { color: "rgba(255,255,255,0.04)" },
          },
          rightPriceScale: {
            borderColor: "rgba(255,255,255,0.08)",
            scaleMargins: { top: 0.1, bottom: 0.1 },
          },
          timeScale: {
            borderColor: "rgba(255,255,255,0.08)",
            timeVisible: true,
            secondsVisible: false,
          },
          crosshair: { mode: 1 },
        });

        chart = newChart;

        const series = newChart.addSeries(lc.CandlestickSeries, {
          upColor: "#00d084",
          downColor: "#ef4444",
          borderVisible: false,
          wickUpColor: "#00d084",
          wickDownColor: "#ef4444",
        });

        if (!cancelled) {
          const resp = await getBars(symbol, timeframe, { limit: TF_LIMIT[timeframe] });
          if (!cancelled) {
            const chartData = resp.bars.map((b: BarData) => ({
              time: (new Date(b.time).getTime() / 1000) as import("lightweight-charts").Time,
              open: b.open,
              high: b.high,
              low: b.low,
              close: b.close,
            }));
            series.setData(chartData);
            newChart.timeScale().fitContent();
            setLoading(false);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      chart?.remove();
    };
  }, [symbol, timeframe]);

  return (
    <div style={paneStyles.wrapper}>
      <div style={paneStyles.label}>
        {symbol} · {TF_LABELS[timeframe]}
      </div>
      {loading && <div style={paneStyles.state}>Loading…</div>}
      {error && <div style={{ ...paneStyles.state, color: "var(--color-accent-red)" }}>{error}</div>}
      <div ref={containerRef} style={{ width: "100%", height: 160, display: loading || error ? "none" : "block" }} />
    </div>
  );
}

// ─── Panel ────────────────────────────────────────────────────────────────────

export function MultiTimeframePanel({
  panelId = "mtf",
  defaultSymbol = "AAPL",
}: MultiTimeframePanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [inputSymbol, setInputSymbol] = useState(defaultSymbol);
  const [timeframes] = useState<Timeframe[]>(DEFAULT_TIMEFRAMES);

  const handleApply = useCallback(() => {
    setSymbol(inputSymbol.toUpperCase());
  }, [inputSymbol]);

  const toolbar = (
    <div style={styles.toolbar}>
      <input
        style={styles.symbolInput}
        value={inputSymbol}
        onChange={(e) => setInputSymbol(e.target.value.toUpperCase())}
        placeholder="AAPL"
        onKeyDown={(e) => e.key === "Enter" && handleApply()}
        aria-label="MTF symbol"
        spellCheck={false}
      />
      <button style={styles.applyBtn} onClick={handleApply} aria-label="Apply symbol">
        GO
      </button>
    </div>
  );

  return (
    <Panel id={panelId} title="MULTI-TIMEFRAME" toolbar={toolbar}>
      <div style={styles.grid}>
        {timeframes.map((tf) => (
          <ChartPane key={`${symbol}-${tf}`} symbol={symbol} timeframe={tf} />
        ))}
      </div>
    </Panel>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  toolbar: { display: "flex", gap: 4, alignItems: "center" },
  symbolInput: {
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-bg-border)",
    borderRadius: 3,
    padding: "2px 7px",
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-primary)",
    outline: "none",
    width: 70,
    textTransform: "uppercase" as const,
  },
  applyBtn: {
    background: "var(--color-accent-blue-bg)",
    border: "1px solid rgba(14,165,233,0.3)",
    borderRadius: 3,
    padding: "2px 8px",
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-blue)",
    cursor: "pointer",
    letterSpacing: "0.06em",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 2,
  },
};

const paneStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    background: "var(--color-bg-elevated)",
    borderRadius: 3,
    overflow: "hidden",
    position: "relative",
  },
  label: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-muted)",
    padding: "3px 6px",
    borderBottom: "1px solid var(--color-bg-separator)",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
  },
  state: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: 160,
    fontSize: 10,
    fontFamily: "var(--font-mono)",
    color: "var(--color-text-muted)",
  },
};
