"use client";

/**
 * ChartPanel — the flagship trading chart panel.
 *
 * Features:
 *   - TradingView Lightweight Charts v5 (candlestick, HA, bar, line, area, baseline)
 *   - All timeframes: 1m, 5m, 15m, 1h, 4h, 1d, 1w
 *   - Real-time price updates from useMarketData → marketDataStore
 *   - Panel configuration persisted in chartStore
 *   - Fibonacci retracement and Trendline drawing tools (drawings persisted in chartStore)
 */

import React, {
  useEffect,
  useState,
  useCallback,
  useRef,
  forwardRef,
  useImperativeHandle,
} from "react";
import { Panel } from "@/components/layout/Panel";
import { ChartCanvas } from "./ChartCanvas";
import { ChartToolbar } from "./ChartToolbar";
import { useChartStore } from "@/store/chartStore";
import { useMarketDataStore } from "@/store/marketDataStore";
import { getBars } from "@/lib/api/market";
import type { BarData } from "@/lib/api/market";
import type { Timeframe } from "@/types/market";
import type { ChartType } from "@/store/chartStore";
import type { Quote } from "@/types/market";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import { useFibonacciTool } from "./useFibonacciTool";
import { useTrendlineTool } from "./useTrendlineTool";

// ─── ChartCanvas imperative handle ──────────────────────────────────────────

export interface ChartCanvasHandle {
  chartRef: React.RefObject<IChartApi | null>;
  seriesRef: React.RefObject<ISeriesApi<
    "Candlestick" | "Line" | "Area" | "Bar" | "Baseline"
  > | null>;
}

interface ChartPanelProps {
  panelId?: string;
}

export function ChartPanel({ panelId = "chart" }: ChartPanelProps) {
  const {
    panels,
    setSymbol,
    setTimeframe,
    setChartType,
    addIndicator,
    removeIndicator,
    toggleIndicator,
    setDrawings,
  } = useChartStore();

  const config = panels[panelId] ?? {
    symbol: "AAPL",
    timeframe: "1d" as Timeframe,
    chartType: "candlestick" as ChartType,
    indicators: [],
    drawings: { fib: [], trendline: [] },
  };

  const [bars, setBars] = useState<BarData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Shared chart + series refs — lifted up so drawing tools can access them
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<
    "Candlestick" | "Line" | "Area" | "Bar" | "Baseline"
  > | null>(null);

  // Subscribe to live price ticks for the active symbol
  const latestQuote: Quote | undefined = useMarketDataStore(
    (s) => s.quotes[config.symbol]
  );

  // Drawing tools
  const fib = useFibonacciTool(chartRef, seriesRef);
  const trendline = useTrendlineTool(chartRef, bars, seriesRef);

  // Persist drawings when they change
  useEffect(() => {
    if (setDrawings) {
      setDrawings(panelId, { fib: fib.drawings, trendline: trendline.drawings });
    }
  }, [fib.drawings, trendline.drawings, panelId, setDrawings]);

  // Fetch bars when symbol or timeframe changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getBars(config.symbol, config.timeframe, { limit: 300 })
      .then((resp) => {
        if (!cancelled) {
          setBars(resp.bars);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [config.symbol, config.timeframe]);

  const handleSymbolChange = useCallback(
    (sym: string) => setSymbol(panelId, sym),
    [panelId, setSymbol]
  );
  const handleTimeframeChange = useCallback(
    (tf: Timeframe) => setTimeframe(panelId, tf),
    [panelId, setTimeframe]
  );
  const handleChartTypeChange = useCallback(
    (type: ChartType) => setChartType(panelId, type),
    [panelId, setChartType]
  );
  const handleAddIndicator = useCallback(
    (ind: import("@/store/chartStore").IndicatorConfig) => addIndicator(panelId, ind),
    [panelId, addIndicator]
  );
  const handleRemoveIndicator = useCallback(
    (id: string) => removeIndicator(panelId, id),
    [panelId, removeIndicator]
  );
  const handleToggleIndicator = useCallback(
    (id: string) => toggleIndicator(panelId, id),
    [panelId, toggleIndicator]
  );

  // Drawing tool callbacks
  const handleFibToggle = useCallback(() => {
    if (fib.isActive) {
      fib.deactivate();
    } else {
      trendline.deactivate(); // deactivate the other tool first
      fib.activate();
    }
  }, [fib, trendline]);

  const handleTrendToggle = useCallback(() => {
    if (trendline.isActive) {
      trendline.deactivate();
    } else {
      fib.deactivate(); // deactivate the other tool first
      trendline.activate();
    }
  }, [fib, trendline]);

  const handleClearDrawings = useCallback(() => {
    fib.clear();
    trendline.clear();
  }, [fib, trendline]);

  const toolbar = (
    <ChartToolbar
      symbol={config.symbol}
      timeframe={config.timeframe}
      chartType={config.chartType}
      indicators={config.indicators}
      onSymbolChange={handleSymbolChange}
      onTimeframeChange={handleTimeframeChange}
      onChartTypeChange={handleChartTypeChange}
      onAddIndicator={handleAddIndicator}
      onRemoveIndicator={handleRemoveIndicator}
      onToggleIndicator={handleToggleIndicator}
      fibActive={fib.isActive}
      trendActive={trendline.isActive}
      onFibToggle={handleFibToggle}
      onTrendToggle={handleTrendToggle}
      onClearDrawings={handleClearDrawings}
    />
  );

  return (
    <Panel id={panelId} title={`${config.symbol} · ${config.timeframe.toUpperCase()}`}>
      {toolbar}
      {loading && (
        <div style={styles.state}>
          <span style={styles.loadingText}>Loading {config.symbol}…</span>
        </div>
      )}
      {error && !loading && (
        <div style={styles.state}>
          <span style={styles.errorText}>{error}</span>
        </div>
      )}
      {!loading && !error && (
        <ChartCanvas
          bars={bars}
          chartType={config.chartType}
          latestQuote={latestQuote}
          indicators={config.indicators}
          height={420}
          chartRef={chartRef}
          seriesRef={seriesRef}
        />
      )}
    </Panel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  state: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: 420,
  },
  loadingText: {
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    color: "var(--color-text-muted)",
    letterSpacing: "0.06em",
  },
  errorText: {
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    color: "var(--color-accent-red)",
  },
};
