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
import { PointAndFigureCanvas } from "./PointAndFigureCanvas";
import { KagiCanvas } from "./KagiCanvas";
import { useChartStore } from "@/store/chartStore";
import { useMarketDataStore } from "@/store/marketDataStore";
import { getBars, getVPVR } from "@/lib/api/market";
import type { BarData } from "@/lib/api/market";
import type { VPVRLevel } from "./ChartCanvas";
import type { Timeframe } from "@/types/market";
import type { ChartType } from "@/store/chartStore";
import type { Quote } from "@/types/market";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import { useFibonacciTool } from "./useFibonacciTool";
import { useTrendlineTool } from "./useTrendlineTool";
import { usePitchforkTool } from "./usePitchforkTool";
import { useAnnotationTool } from "./useAnnotationTool";
import { useGannFanTool } from "./useGannFanTool";
import { useElliottWaveTool } from "./useElliottWaveTool";
import { useRegimeOverlay } from "@/hooks/useRegimeOverlay";

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
    drawings: { fib: [], trendline: [], pitchfork: [], annotations: [] },
  };

  const [bars, setBars] = useState<BarData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vpvr, setVpvr] = useState<VPVRLevel[] | undefined>(undefined);

  // Shared chart + series refs — lifted up so drawing tools can access them
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<
    "Candlestick" | "Line" | "Area" | "Bar" | "Baseline"
  > | null>(null);

  // Subscribe to live price ticks for the active symbol
  const latestQuote: Quote | undefined = useMarketDataStore(
    (s) => s.quotes[config.symbol]
  );

  const { regime } = useRegimeOverlay(config.symbol);

  // Drawing tools
  const fib = useFibonacciTool(chartRef, seriesRef);
  const trendline = useTrendlineTool(chartRef, bars, seriesRef);
  const pitchfork = usePitchforkTool(chartRef, bars, seriesRef);
  const annotation = useAnnotationTool(chartRef, seriesRef);
  const gannFan = useGannFanTool(chartRef, bars, seriesRef);
  const elliottWave = useElliottWaveTool(chartRef, bars, seriesRef);

  // Canvas chart dimensions state
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const [canvasDims, setCanvasDims] = useState({ width: 600, height: 420 });

  useEffect(() => {
    const el = canvasContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setCanvasDims({
          width: Math.floor(entry.contentRect.width),
          height: Math.floor(entry.contentRect.height),
        });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Persist drawings when they change
  useEffect(() => {
    if (setDrawings) {
      setDrawings(panelId, {
        fib: fib.drawings,
        trendline: trendline.drawings,
        pitchfork: pitchfork.drawings,
        annotations: annotation.drawings,
        gannFan: gannFan.drawings,
        elliottWave: elliottWave.drawings,
      });
    }
  }, [fib.drawings, trendline.drawings, pitchfork.drawings, annotation.drawings, gannFan.drawings, elliottWave.drawings, panelId, setDrawings]);

  // Fetch bars when symbol, timeframe, or chartType changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const barsOptions: { limit: number; chart_type?: string; brick_size?: number } = { limit: 300 };
    if (config.chartType === "renko") {
      barsOptions.chart_type = "renko";
      barsOptions.brick_size = 1.0;
    } else if (config.chartType === "line_break") {
      barsOptions.chart_type = "line_break";
    }

    getBars(config.symbol, config.timeframe, barsOptions)
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
  }, [config.symbol, config.timeframe, config.chartType]);

  // Fetch VPVR when symbol or timeframe changes
  useEffect(() => {
    let cancelled = false;
    getVPVR(config.symbol, config.timeframe)
      .then((data) => {
        if (!cancelled) setVpvr(data.price_levels);
      })
      .catch(() => {
        if (!cancelled) setVpvr(undefined);
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

  const handlePitchforkToggle = useCallback(() => {
    if (pitchfork.isActive) {
      pitchfork.deactivate();
    } else {
      fib.deactivate();
      trendline.deactivate();
      annotation.deactivate();
      pitchfork.activate();
    }
  }, [pitchfork, fib, trendline, annotation]);

  const handleAnnotationToggle = useCallback(() => {
    if (annotation.isActive) {
      annotation.deactivate();
    } else {
      fib.deactivate();
      trendline.deactivate();
      pitchfork.deactivate();
      annotation.activate();
    }
  }, [annotation, fib, trendline, pitchfork]);

  const handleGannFanToggle = useCallback(() => {
    if (gannFan.isActive) {
      gannFan.deactivate();
    } else {
      fib.deactivate();
      trendline.deactivate();
      pitchfork.deactivate();
      annotation.deactivate();
      elliottWave.deactivate();
      gannFan.activate();
    }
  }, [gannFan, fib, trendline, pitchfork, annotation, elliottWave]);

  const handleElliottWaveToggle = useCallback(
    (mode: "impulse" | "corrective") => {
      if (elliottWave.isActive && elliottWave.mode === mode) {
        elliottWave.deactivate();
      } else {
        fib.deactivate();
        trendline.deactivate();
        pitchfork.deactivate();
        annotation.deactivate();
        gannFan.deactivate();
        elliottWave.activate(mode);
      }
    },
    [elliottWave, fib, trendline, pitchfork, annotation, gannFan]
  );

  const handleClearDrawings = useCallback(() => {
    fib.clear();
    trendline.clear();
    pitchfork.clear();
    annotation.clear();
    gannFan.clear();
    elliottWave.clear();
  }, [fib, trendline, pitchfork, annotation, gannFan, elliottWave]);

  const isPriceAxisChart = config.chartType !== "pnf" && config.chartType !== "kagi";

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
      pitchforkActive={pitchfork.isActive}
      annotationActive={annotation.isActive}
      gannFanActive={gannFan.isActive}
      elliottWaveActive={elliottWave.isActive}
      elliottWaveMode={elliottWave.mode}
      onFibToggle={handleFibToggle}
      onTrendToggle={handleTrendToggle}
      onPitchforkToggle={handlePitchforkToggle}
      onAnnotationToggle={handleAnnotationToggle}
      onGannFanToggle={handleGannFanToggle}
      onElliottWaveToggle={handleElliottWaveToggle}
      onClearDrawings={handleClearDrawings}
    />
  );

  return (
    <Panel id={panelId} title={`${config.symbol} · ${config.timeframe.toUpperCase()}`}>
      {toolbar}
      {regime && isPriceAxisChart && (
        <div style={styles.regimeBadge}>
          <span style={{
            ...styles.regimePill,
            background: regime === "bull" ? "rgba(0,208,132,0.15)" : regime === "bear" ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)",
            color: regime === "bull" ? "#00d084" : regime === "bear" ? "#ef4444" : "#f59e0b",
            border: `1px solid ${regime === "bull" ? "#00d084" : regime === "bear" ? "#ef4444" : "#f59e0b"}`,
          }}>
            {regime === "bull" ? "🟢 Bull Regime" : regime === "bear" ? "🔴 Bear Regime" : "🟡 Sideways"}
          </span>
        </div>
      )}
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
        <>
          {/* Standard lightweight-charts view (candlestick, line, etc.) */}
          <div style={{ display: isPriceAxisChart ? "block" : "none" }}>
            <ChartCanvas
              bars={bars}
              chartType={config.chartType}
              latestQuote={latestQuote}
              indicators={config.indicators}
              height={420}
              chartRef={chartRef}
              seriesRef={seriesRef}
              vpvr={vpvr}
            />
          </div>

          {/* Canvas-based chart types (P&F, Kagi) — shown when selected */}
          {!isPriceAxisChart && (
            <div
              ref={canvasContainerRef}
              style={{ width: "100%", height: 420, overflow: "hidden" }}
            >
              {config.chartType === "pnf" && (
                <PointAndFigureCanvas
                  bars={bars}
                  width={canvasDims.width || 600}
                  height={canvasDims.height || 420}
                />
              )}
              {config.chartType === "kagi" && (
                <KagiCanvas
                  bars={bars}
                  width={canvasDims.width || 600}
                  height={canvasDims.height || 420}
                />
              )}
            </div>
          )}
        </>
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
  regimeBadge: { padding: "2px 8px" },
  regimePill: { fontSize: 10, borderRadius: 10, padding: "1px 8px", fontFamily: "var(--font-mono)" },
};
