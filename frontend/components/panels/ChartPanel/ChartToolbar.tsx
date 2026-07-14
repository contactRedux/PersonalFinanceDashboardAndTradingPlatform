"use client";

/**
 * ChartToolbar — timeframe selector, chart type toggle, symbol input,
 * and indicator overlay manager.
 */

import React, { useState, useCallback, useRef, useEffect } from "react";
import type { Timeframe } from "@/types/market";
import type { ChartType, IndicatorConfig } from "@/store/chartStore";

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

const INDICATOR_TYPES: { label: string; type: string; defaultParams: Record<string, number> }[] = [
  { label: "SMA", type: "sma", defaultParams: { period: 20 } },
  { label: "EMA", type: "ema", defaultParams: { period: 20 } },
  { label: "WMA", type: "wma", defaultParams: { period: 20 } },
  { label: "BB", type: "bb", defaultParams: { period: 20, std_dev: 2 } },
  { label: "RSI", type: "rsi", defaultParams: { period: 14 } },
  { label: "MACD", type: "macd", defaultParams: { fast: 12, slow: 26, signal: 9 } },
];

interface ChartToolbarProps {
  symbol: string;
  timeframe: Timeframe;
  chartType: ChartType;
  indicators: IndicatorConfig[];
  onSymbolChange: (symbol: string) => void;
  onTimeframeChange: (tf: Timeframe) => void;
  onChartTypeChange: (type: ChartType) => void;
  onAddIndicator: (indicator: IndicatorConfig) => void;
  onRemoveIndicator: (id: string) => void;
  onToggleIndicator: (id: string) => void;
  // Drawing tool state
  fibActive?: boolean;
  trendActive?: boolean;
  onFibToggle?: () => void;
  onTrendToggle?: () => void;
  onClearDrawings?: () => void;
}

export function ChartToolbar({
  symbol,
  timeframe,
  chartType,
  indicators,
  onSymbolChange,
  onTimeframeChange,
  onChartTypeChange,
  onAddIndicator,
  onRemoveIndicator,
  onToggleIndicator,
  fibActive = false,
  trendActive = false,
  onFibToggle,
  onTrendToggle,
  onClearDrawings,
}: ChartToolbarProps) {
  const [symbolInput, setSymbolInput] = useState(symbol);
  const [indMenuOpen, setIndMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIndMenuOpen(false);
      }
    }
    if (indMenuOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [indMenuOpen]);

  const handleSymbolSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const s = symbolInput.trim().toUpperCase();
      if (s) onSymbolChange(s);
    },
    [symbolInput, onSymbolChange]
  );

  const handleAddIndicator = useCallback(
    (type: string, defaultParams: Record<string, number>) => {
      const id = `${type}-${Date.now()}`;
      onAddIndicator({ id, type, params: defaultParams, visible: true });
      setIndMenuOpen(false);
    },
    [onAddIndicator]
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

      {/* Separator */}
      <div style={styles.sep} />

      {/* Indicator dropdown */}
      <div ref={menuRef} style={styles.indWrapper}>
        <button
          style={{
            ...styles.btn,
            ...(indMenuOpen ? styles.btnActive : {}),
          }}
          onClick={() => setIndMenuOpen((v) => !v)}
          aria-label="Add indicator"
          aria-expanded={indMenuOpen}
        >
          Ind ▾
        </button>

        {indMenuOpen && (
          <div style={styles.indMenu} role="menu">
            {INDICATOR_TYPES.map(({ label, type, defaultParams }) => (
              <button
                key={type}
                style={styles.indMenuItem}
                role="menuitem"
                onClick={() => handleAddIndicator(type, defaultParams)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Active indicator pills */}
      {indicators.length > 0 && (
        <>
          <div style={styles.sep} />
          <div style={styles.pillGroup}>
            {indicators.map((ind) => (
              <div key={ind.id} style={styles.pill}>
                <button
                  style={{
                    ...styles.pillLabel,
                    opacity: ind.visible ? 1 : 0.4,
                  }}
                  onClick={() => onToggleIndicator(ind.id)}
                  title={ind.visible ? "Hide" : "Show"}
                  aria-label={`Toggle ${ind.type}`}
                >
                  {ind.type.toUpperCase()}
                  {ind.params.period ? `(${ind.params.period})` : ""}
                </button>
                <button
                  style={styles.pillRemove}
                  onClick={() => onRemoveIndicator(ind.id)}
                  aria-label={`Remove ${ind.type}`}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Drawing tools */}
      {(onFibToggle || onTrendToggle) && (
        <>
          <div style={styles.sep} />
          <div style={styles.group}>
            {onFibToggle && (
              <button
                style={{ ...styles.btn, ...(fibActive ? styles.btnActive : {}) }}
                onClick={onFibToggle}
                aria-label="Fibonacci retracement tool"
                aria-pressed={fibActive}
                title="Fibonacci Retracement: click swing high then swing low"
              >
                Fib
              </button>
            )}
            {onTrendToggle && (
              <button
                style={{ ...styles.btn, ...(trendActive ? styles.btnActive : {}) }}
                onClick={onTrendToggle}
                aria-label="Trendline tool"
                aria-pressed={trendActive}
                title="Trendline: click two points to draw"
              >
                Trend
              </button>
            )}
            {onClearDrawings && (fibActive || trendActive) && (
              <button
                style={{ ...styles.btn, color: "#ef4444", borderColor: "rgba(239,68,68,0.3)" }}
                onClick={onClearDrawings}
                aria-label="Clear all drawings"
                title="Clear all drawings"
              >
                ✕ Clear
              </button>
            )}
          </div>
        </>
      )}
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
  indWrapper: {
    position: "relative" as const,
  },
  indMenu: {
    position: "absolute" as const,
    top: "calc(100% + 4px)",
    left: 0,
    background: "#141414",
    border: "1px solid #2a2a2a",
    borderRadius: 4,
    zIndex: 100,
    minWidth: 80,
    padding: 2,
    display: "flex",
    flexDirection: "column" as const,
    gap: 1,
  },
  indMenuItem: {
    background: "transparent",
    border: "none",
    padding: "4px 10px",
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#c0c0c0",
    cursor: "pointer",
    textAlign: "left" as const,
    borderRadius: 3,
    letterSpacing: "0.04em",
  },
  pillGroup: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 4,
  },
  pill: {
    display: "flex",
    alignItems: "center",
    background: "rgba(255,255,255,0.06)",
    border: "1px solid #2a2a2a",
    borderRadius: 10,
    overflow: "hidden",
  },
  pillLabel: {
    background: "transparent",
    border: "none",
    padding: "1px 6px",
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    color: "#aaa",
    cursor: "pointer",
    letterSpacing: "0.04em",
  },
  pillRemove: {
    background: "transparent",
    border: "none",
    padding: "0 5px",
    fontSize: 11,
    color: "#555",
    cursor: "pointer",
    lineHeight: 1,
  },
};
