"use client";

/**
 * ChartCanvas — mounts a TradingView Lightweight Charts v5 instance.
 *
 * Receives OHLCV bars as props and renders candlestick/line/area/bar/baseline.
 * Handles resize via ResizeObserver.
 * Receives real-time tick updates via onTick prop.
 */

import { useEffect, useRef } from "react";
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
import type { ChartType } from "@/store/chartStore";
import { heikinAshi } from "@/lib/indicators";

interface ChartCanvasProps {
  bars: BarData[];
  chartType: ChartType;
  latestQuote?: Quote;
  height?: number;
}

export function ChartCanvas({ bars, chartType, latestQuote, height = 420 }: ChartCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>(null);

  // Initialize chart on mount
  useEffect(() => {
    if (!containerRef.current) return;

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
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Add/swap series when chartType or bars change
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Remove existing series
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

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: height,
        background: "#0a0a0a",
        borderRadius: 0,
      }}
    />
  );
}
