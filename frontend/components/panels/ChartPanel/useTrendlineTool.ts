"use client";

/**
 * Trendline drawing tool for lightweight-charts.
 *
 * Usage:
 *   const trendline = useTrendlineTool(chartRef, bars);
 *   trendline.activate();    // Click 2 points → trendline drawn + extended
 *   trendline.clear();       // Remove all trendlines
 *   trendline.isActive       // true while awaiting clicks
 *   trendline.drawings       // current trendlines (persist to workspace)
 *
 * Line extension: slope calculated from 2 points, extended to the last bar.
 * Hover tooltip: shows interpolated price at cursor via crosshairMove subscription.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";

export interface TrendlineDrawing {
  id: string;
  point1: { time: number; price: number };
  point2: { time: number; price: number };
}

interface TrendlineTool {
  activate: () => void;
  deactivate: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  drawings: TrendlineDrawing[];
  hoverPrice: number | null;
}

export function useTrendlineTool(
  chartRef: React.RefObject<IChartApi | null>,
  bars: BarData[],
  seriesRef?: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): TrendlineTool {
  const [isActive, setIsActive] = useState(false);
  const [drawings, setDrawings] = useState<TrendlineDrawing[]>([]);
  const [hoverPrice, setHoverPrice] = useState<number | null>(null);

  const stateRef = useRef<"idle" | "waiting_point1" | "waiting_point2">("idle");
  const point1Ref = useRef<{ time: number; price: number } | null>(null);

  // Map drawing ID → LineSeries
  const lineSeriesRef = useRef<
    Map<string, ISeriesApi<"Line">>
  >(new Map());

  // Import LineSeries lazily to avoid SSR issues
  const { LineSeries } = require("lightweight-charts") as typeof import("lightweight-charts");

  const extendToPresent = useCallback(
    (
      p1: { time: number; price: number },
      p2: { time: number; price: number }
    ): { time: number; price: number }[] => {
      if (bars.length === 0) return [p1, p2];
      const lastBarTime = new Date(bars[bars.length - 1].time).getTime() / 1000;
      const dTime = p2.time - p1.time;
      if (dTime === 0) return [p1, p2];
      const slope = (p2.price - p1.price) / dTime;
      const extendedPrice = p1.price + slope * (lastBarTime - p1.time);
      return [
        { time: p1.time, price: p1.price },
        { time: lastBarTime, price: extendedPrice },
      ];
    },
    [bars]
  );

  const drawTrendline = useCallback(
    (
      p1: { time: number; price: number },
      p2: { time: number; price: number }
    ): TrendlineDrawing => {
      const id = `trend-${Date.now()}`;
      const chart = chartRef.current;
      if (chart) {
        const points = extendToPresent(p1, p2);
        const series = chart.addSeries(LineSeries, {
          color: "#00d084",
          lineWidth: 1,
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        series.setData(
          points.map(({ time, price }) => ({
            time: time as Time,
            value: price,
          }))
        );
        lineSeriesRef.current.set(id, series);
      }
      return { id, point1: p1, point2: p2 };
    },
    [chartRef, extendToPresent, LineSeries]
  );

  const removeTrendlineSeries = useCallback(
    (id: string) => {
      const chart = chartRef.current;
      const series = lineSeriesRef.current.get(id);
      if (chart && series) {
        try {
          chart.removeSeries(series);
        } catch {
          // Series may already be gone
        }
      }
      lineSeriesRef.current.delete(id);
    },
    [chartRef]
  );

  // Subscribe to click events when active
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isActive) return;

    const handleClick = (param: { point?: { x: number; y: number }; time?: Time }) => {
      if (!param.point || !param.time) return;
      // Use the primary series' coordinateToPrice (v5 API), falling back to
      // lineSeriesRef's first entry if seriesRef is not provided
      const primarySeries = seriesRef?.current
        ?? (lineSeriesRef.current.size > 0
          ? lineSeriesRef.current.values().next().value
          : null);
      if (!primarySeries) return;

      const price = primarySeries.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      const timeNum = typeof param.time === "number"
        ? param.time
        : (param.time as unknown as number);

      if (stateRef.current === "waiting_point1") {
        point1Ref.current = { time: timeNum, price };
        stateRef.current = "waiting_point2";
        return;
      }

      if (stateRef.current === "waiting_point2" && point1Ref.current !== null) {
        const drawing = drawTrendline(point1Ref.current, { time: timeNum, price });
        setDrawings((prev) => [...prev, drawing]);
        stateRef.current = "idle";
        point1Ref.current = null;
        setIsActive(false);
      }
    };

    chart.subscribeClick(handleClick);
    return () => chart.unsubscribeClick(handleClick);
  }, [isActive, chartRef, drawTrendline]);

  // Crosshair hover → show interpolated price on active trendlines
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const handleCrosshair = (param: { point?: { x: number; y: number }; time?: Time }) => {
      if (!param.time || !param.point) {
        setHoverPrice(null);
        return;
      }
      // Resolve a series to get a pixel→price conversion
      const anySeries = seriesRef?.current
        ?? (lineSeriesRef.current.size > 0
          ? lineSeriesRef.current.values().next().value
          : null);
      if (!anySeries) {
        setHoverPrice(null);
        return;
      }
      const price = anySeries.coordinateToPrice(param.point.y);
      setHoverPrice(price ?? null);
    };

    chart.subscribeCrosshairMove(handleCrosshair);
    return () => chart.unsubscribeCrosshairMove(handleCrosshair);
  }, [chartRef]);

  const activate = useCallback(() => {
    stateRef.current = "waiting_point1";
    point1Ref.current = null;
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    stateRef.current = "idle";
    point1Ref.current = null;
    setIsActive(false);
  }, []);

  const clear = useCallback(() => {
    for (const id of lineSeriesRef.current.keys()) {
      removeTrendlineSeries(id);
    }
    setDrawings([]);
  }, [removeTrendlineSeries]);

  const removeDrawing = useCallback(
    (id: string) => {
      removeTrendlineSeries(id);
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removeTrendlineSeries]
  );

  return { activate, deactivate, clear, removeDrawing, isActive, drawings, hoverPrice };
}
