"use client";

/**
 * ChartCanvas — mounts a TradingView Lightweight Charts v5 instance.
 *
 * Receives OHLCV bars as props and renders candlestick/line/area/bar/baseline.
 * Handles resize via autoSize.
 * Receives real-time tick updates via latestQuote prop.
 * Renders indicator overlays (SMA, EMA, WMA, BB, RSI, MACD) as LineSeries.
 */

import React, { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  BarSeries,
  BaselineSeries,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time, CandlestickData, OhlcData } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";
import type { Quote } from "@/types/market";
import type { ChartType, IndicatorConfig } from "@/store/chartStore";
import {
  sma,
  ema,
  wma,
  bollingerBands,
  rsi,
  macd,
  heikinAshi,
} from "@/lib/indicators";

// Colour palette for overlay series
const OVERLAY_COLOURS = [
  "#f59e0b", // amber
  "#3b82f6", // blue
  "#a855f7", // purple
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316", // orange
];

let _colourIdx = 0;
function nextColour(): string {
  return OVERLAY_COLOURS[_colourIdx++ % OVERLAY_COLOURS.length];
}

interface VPVRLevel {
  price: number;
  volume: number;
  is_poc: boolean;
  pct_of_max: number;
}

interface ChartCanvasProps {
  bars: BarData[];
  chartType: ChartType;
  latestQuote?: Quote;
  height?: number;
  indicators?: IndicatorConfig[];
  /** Optional VPVR data rendered as a canvas overlay on the right side. */
  vpvr?: VPVRLevel[];
  /**
   * If provided, ChartCanvas will populate these refs so the parent (ChartPanel)
   * can share them with drawing-tool hooks.
   */
  chartRef?: React.RefObject<IChartApi | null>;
  seriesRef?: React.RefObject<ISeriesApi<
    "Candlestick" | "Line" | "Area" | "Bar" | "Baseline"
  > | null>;
}

export function ChartCanvas({
  bars,
  chartType,
  latestQuote,
  height = 420,
  indicators = [],
  vpvr,
  chartRef: externalChartRef,
  seriesRef: externalSeriesRef,
}: ChartCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const internalChartRef = useRef<IChartApi | null>(null);
  const internalSeriesRef = useRef<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>(
    null
  );

  // Resolve to external refs if provided, otherwise use internal refs
  const chartRef = externalChartRef ?? internalChartRef;
  const seriesRef = externalSeriesRef ?? internalSeriesRef;
  // Map: indicator id (or id+"_upper" etc.) → LineSeries
  const overlayRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const vpvrCanvasRef = useRef<HTMLCanvasElement>(null);

  // Initialize chart on mount
  useEffect(() => {
    if (!containerRef.current) return;

    _colourIdx = 0; // reset colour rotation on remount
    // Capture overlay map at effect-start so the cleanup closure holds a stable ref
    const overlays = overlayRef.current;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "#0a0a0a" },
        textColor: "#8a8a8a",
        fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1a1a1a", style: 1 },
        horzLines: { color: "#1a1a1a", style: 1 },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: "#555555", width: 1, style: 3, labelBackgroundColor: "#222" },
        horzLine: { color: "#555555", width: 1, style: 3, labelBackgroundColor: "#222" },
      },
      rightPriceScale: {
        borderColor: "#222222",
        textColor: "#8a8a8a",
      },
      timeScale: {
        borderColor: "#222222",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    chartRef.current = chart;

    return () => {
      overlays.clear();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Add/swap primary series when chartType or bars change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove all overlay series before recreating primary (chart.remove() resets everything)
    overlayRef.current.forEach((s) => chart.removeSeries(s));
    overlayRef.current.clear();

    // Remove existing primary series
    if (seriesRef.current) {
      chart.removeSeries(seriesRef.current);
      seriesRef.current = null;
    }

    if (!bars.length) return;

    const commonOptions = {
      priceLineVisible: true,
      lastValueVisible: true,
    };

    if (chartType === "candlestick" || chartType === "heikin_ashi") {
      const series = chart.addSeries(CandlestickSeries, {
        ...commonOptions,
        upColor: "#00d084",
        downColor: "#ef4444",
        borderUpColor: "#00d084",
        borderDownColor: "#ef4444",
        wickUpColor: "#00a868",
        wickDownColor: "#dc2626",
      });

      let ohlcBars = bars.map((b) => ({
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));

      if (chartType === "heikin_ashi") {
        ohlcBars = heikinAshi(ohlcBars);
      }

      const data: CandlestickData<Time>[] = bars.map((b, i) => ({
        time: (new Date(b.time).getTime() / 1000) as Time,
        open: ohlcBars[i].open,
        high: ohlcBars[i].high,
        low: ohlcBars[i].low,
        close: ohlcBars[i].close,
      }));
      series.setData(data);
      seriesRef.current = series;
    } else if (chartType === "bar") {
      const series = chart.addSeries(BarSeries, {
        ...commonOptions,
        upColor: "#00d084",
        downColor: "#ef4444",
      });
      const data: OhlcData<Time>[] = bars.map((b) => ({
        time: (new Date(b.time).getTime() / 1000) as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
      series.setData(data);
      seriesRef.current = series;
    } else if (chartType === "area") {
      const series = chart.addSeries(AreaSeries, {
        ...commonOptions,
        lineColor: "#0ea5e9",
        topColor: "rgba(14,165,233,0.3)",
        bottomColor: "rgba(14,165,233,0.01)",
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    } else if (chartType === "baseline") {
      const series = chart.addSeries(BaselineSeries, {
        ...commonOptions,
        baseValue: { type: "price", price: bars[0]?.close ?? 0 },
        topLineColor: "#00d084",
        topFillColor1: "rgba(0,208,132,0.2)",
        topFillColor2: "rgba(0,208,132,0.02)",
        bottomLineColor: "#ef4444",
        bottomFillColor1: "rgba(239,68,68,0.02)",
        bottomFillColor2: "rgba(239,68,68,0.2)",
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    } else {
      // line (default)
      const series = chart.addSeries(LineSeries, {
        ...commonOptions,
        color: "#0ea5e9",
        lineWidth: 2,
      });
      series.setData(
        bars.map((b) => ({
          time: (new Date(b.time).getTime() / 1000) as Time,
          value: b.close,
        }))
      );
      seriesRef.current = series;
    }

    chart.timeScale().fitContent();
  }, [bars, chartType]);

  // Indicator overlays — diff and update when indicators or bars change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !bars.length) return;

    const times = bars.map((b) => (new Date(b.time).getTime() / 1000) as Time);
    const closes = bars.map((b) => b.close);

    const currentIds = new Set<string>();

    for (const ind of indicators) {
      if (ind.type === "bb") {
        // Bollinger Bands — three sub-series per indicator id
        const period = (ind.params.period as number) ?? 20;
        const stdDev = (ind.params.std_dev as number) ?? 2;
        const bb = bollingerBands(closes, period, stdDev);
        const colour = nextColour();

        for (const band of ["upper", "mid", "lower"] as const) {
          const key = `${ind.id}_${band}`;
          currentIds.add(key);
          if (!overlayRef.current.has(key)) {
            const s = chart.addSeries(LineSeries, {
              color: colour,
              lineWidth: 1,
              lineStyle: band === "mid" ? 0 : 2,
              visible: ind.visible,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(key, s);
          }
          const series = overlayRef.current.get(key)!;
          series.applyOptions({ visible: ind.visible });
          const values = band === "upper" ? bb.upper : band === "mid" ? bb.middle : bb.lower;
          series.setData(
            times
              .map((t, i) => ({ time: t, value: values[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        continue;
      }

      if (ind.type === "macd") {
        // MACD — three sub-series: macd line, signal, histogram
        const fast = (ind.params.fast as number) ?? 12;
        const slow = (ind.params.slow as number) ?? 26;
        const signal = (ind.params.signal as number) ?? 9;
        const result = macd(closes, fast, slow, signal);
        const colour = nextColour();

        for (const part of ["line", "signal", "hist"] as const) {
          const key = `${ind.id}_${part}`;
          currentIds.add(key);
          if (!overlayRef.current.has(key)) {
            const s = chart.addSeries(LineSeries, {
              color: part === "hist" ? "rgba(255,255,255,0.35)" : colour,
              lineWidth: part === "hist" ? 1 : 1,
              lineStyle: part === "signal" ? 2 : 0,
              visible: ind.visible,
              priceScaleId: "macd",
              priceLineVisible: false,
              lastValueVisible: false,
            });
            overlayRef.current.set(key, s);
          }
          const series = overlayRef.current.get(key)!;
          series.applyOptions({ visible: ind.visible });
          const vals =
            part === "line" ? result.macd : part === "signal" ? result.signal : result.histogram;
          series.setData(
            times
              .map((t, i) => ({ time: t, value: vals[i] }))
              .filter((pt) => !isNaN(pt.value))
          );
        }
        // Apply scale margins so MACD renders below price
        chart.priceScale("macd").applyOptions({
          scaleMargins: { top: 0.7, bottom: 0 },
        });
        continue;
      }

      if (ind.type === "rsi") {
        const period = (ind.params.period as number) ?? 14;
        const values = rsi(closes, period);
        const key = ind.id;
        currentIds.add(key);
        if (!overlayRef.current.has(key)) {
          const s = chart.addSeries(LineSeries, {
            color: nextColour(),
            lineWidth: 1,
            visible: ind.visible,
            priceScaleId: "rsi",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          overlayRef.current.set(key, s);
        }
        const series = overlayRef.current.get(key)!;
        series.applyOptions({ visible: ind.visible });
        series.setData(
          times
            .map((t, i) => ({ time: t, value: values[i] }))
            .filter((pt) => !isNaN(pt.value))
        );
        chart.priceScale("rsi").applyOptions({
          scaleMargins: { top: 0.75, bottom: 0 },
        });
        continue;
      }

      // SMA, EMA, WMA — single line overlaid on price pane
      const key = ind.id;
      currentIds.add(key);
      if (!overlayRef.current.has(key)) {
        const s = chart.addSeries(LineSeries, {
          color: nextColour(),
          lineWidth: 1,
          visible: ind.visible,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        overlayRef.current.set(key, s);
      }
      const series = overlayRef.current.get(key)!;
      series.applyOptions({ visible: ind.visible });

      const period = (ind.params.period as number) ?? 20;
      const fn = ind.type === "ema" ? ema : ind.type === "wma" ? wma : sma;
      const values = fn(closes, period);
      series.setData(
        times
          .map((t, i) => ({ time: t, value: values[i] }))
          .filter((pt) => !isNaN(pt.value))
      );
    }

    // Remove series for indicators that were deleted
    for (const key of overlayRef.current.keys()) {
      const baseId = key.replace(/_(upper|mid|lower|line|signal|hist)$/, "");
      if (!currentIds.has(key) && !currentIds.has(baseId)) {
        chart.removeSeries(overlayRef.current.get(key)!);
        overlayRef.current.delete(key);
      }
    }
  }, [indicators, bars]);

  // Imperatively update the last bar with the latest quote (bypasses React state)
  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !latestQuote?.price || !bars.length) return;
    const lastBar = bars[bars.length - 1];
    const lastTime = (new Date(lastBar.time).getTime() / 1000) as Time;

    if (chartType === "candlestick" || chartType === "heikin_ashi" || chartType === "bar") {
      (series as ISeriesApi<"Candlestick">).update({
        time: lastTime,
        open: lastBar.open,
        high: Math.max(lastBar.high, latestQuote.price),
        low: Math.min(lastBar.low, latestQuote.price),
        close: latestQuote.price,
      } as CandlestickData<Time>);
    } else {
      (series as ISeriesApi<"Line">).update({
        time: lastTime,
        value: latestQuote.price,
      } as { time: Time; value: number });
    }
  }, [latestQuote, bars, chartType]);

  // VPVR canvas overlay — drawn right-side histogram
  useEffect(() => {
    const canvas = vpvrCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!vpvr || vpvr.length === 0 || !bars.length) return;

    const barPrices = bars.map((b) => b.close);
    const priceMin = Math.min(...barPrices);
    const priceMax = Math.max(...barPrices);
    const priceRange = priceMax - priceMin || 1;

    const maxBarWidth = 60; // px
    const h = canvas.height;
    const w = canvas.width;

    vpvr.forEach((level) => {
      const barW = Math.round(level.pct_of_max * maxBarWidth);
      const y = Math.round(((priceMax - level.price) / priceRange) * h);
      const barH = Math.max(2, Math.round((h / (vpvr.length || 1)) * 0.8));

      ctx.fillStyle = level.is_poc
        ? "rgba(245,158,11,0.7)"  // amber — point of control
        : "rgba(59,130,246,0.35)"; // blue — normal
      ctx.fillRect(w - barW - 2, y - barH / 2, barW, barH);
    });
  }, [vpvr, bars]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: height,
        background: "#0a0a0a",
        borderRadius: 0,
      }}
    >
      {/* VPVR overlay canvas — transparent, pointer-events: none */}
      <canvas
        ref={vpvrCanvasRef}
        width={80}
        height={height}
        style={{
          position: "absolute",
          right: 50, // leave room for price scale
          top: 0,
          pointerEvents: "none",
        }}
        aria-hidden="true"
        data-testid="vpvr-canvas"
      />
    </div>
  );
}
