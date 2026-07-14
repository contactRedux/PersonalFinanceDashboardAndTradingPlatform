"use client";

/**
 * ChartToolbar — timeframe selector, chart type toggle, symbol input.
 */

import React, { useState, useCallback } from "react";
import type { Timeframe } from "@/types/market";
import type { ChartType } from "@/store/chartStore";

const TIMEFRAMES: { label: string; value: Timeframe }[] = [
  { label: "1m", value: "1m" },
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "1h", value: "1h" },
  { label: "4h", value: "4h" },
  { label: "1D", value: "1d" },
  { label: "1W", value: "1w" },
];

const CHART_TYPES: { label: string; value: ChartType }[] = [
  { label: "Candle", value: "candlestick" },
  { label: "HA", value: "heikin_ashi" },
  { label: "Bar", value: "bar" },
  { label: "Line", value: "line" },
  { label: "Area", value: "area" },
  { label: "Base", value: "baseline" },
];

interface ChartToolbarProps {
  symbol: string;
  timeframe: Timeframe;
  chartType: ChartType;
  onSymbolChange: (symbol: string) => void;
  onTimeframeChange: (tf: Timeframe) => void;
  onChartTypeChange: (type: ChartType) => void;
}

export function ChartToolbar({
  symbol,
  timeframe,
  chartType,
  onSymbolChange,
  onTimeframeChange,
  onChartTypeChange,
}: ChartToolbarProps) {
  const [symbolInput, setSymbolInput] = useState(symbol);

  const handleSymbolSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const s = symbolInput.trim().toUpperCase();
      if (s) onSymbolChange(s);
    },
    [symbolInput, onSymbolChange]
  );

  return (
    <div style={styles.toolbar}>
      {/* Symbol input */}
      <form onSubmit={handleSymbolSubmit} style={styles.symbolForm}>
        <input
          type="text"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          style={styles.symbolInput}
          aria-label="Chart symbol"
          spellCheck={false}
          autoComplete="off"
        />
      </form>

      {/* Separator */}
      <div style={styles.sep} />

      {/* Timeframe buttons */}
      <div style={styles.group}>
        {TIMEFRAMES.map(({ label, value }) => (
          <button
            key={value}
            style={{
              ...styles.btn,
              ...(timeframe === value ? styles.btnActive : {}),
            }}
            onClick={() => onTimeframeChange(value)}
            aria-pressed={timeframe === value}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Separator */}
      <div style={styles.sep} />

      {/* Chart type buttons */}
      <div style={styles.group}>
        {CHART_TYPES.map(({ label, value }) => (
          <button
            key={value}
            style={{
              ...styles.btn,
              ...(chartType === value ? styles.btnActive : {}),
            }}
            onClick={() => onChartTypeChange(value)}
            aria-pressed={chartType === value}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 8px",
    background: "#0d0d0d",
    borderBottom: "1px solid #1a1a1a",
    flexWrap: "wrap",
    flexShrink: 0,
  },
  symbolForm: {
    display: "flex",
    alignItems: "center",
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
    width: 80,
    textTransform: "uppercase" as const,
  },
  group: {
    display: "flex",
    gap: 2,
  },
  btn: {
    padding: "2px 7px",
    background: "transparent",
    border: "1px solid transparent",
    borderRadius: 3,
    fontSize: 10,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#8a8a8a",
    cursor: "pointer",
    letterSpacing: "0.04em",
    transition: "all 0.1s",
  },
  btnActive: {
    background: "rgba(0,208,132,0.12)",
    border: "1px solid rgba(0,208,132,0.3)",
    color: "#00d084",
  },
  sep: {
    width: 1,
    height: 16,
    background: "#222",
  },
};
