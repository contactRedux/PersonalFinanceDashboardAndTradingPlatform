"use client";

/**
 * Andrews' Pitchfork drawing tool for lightweight-charts.
 *
 * Usage:
 *   const pitchfork = usePitchforkTool(chartRef, bars, seriesRef);
 *   pitchfork.activate(); // Click 1 = pivot high, click 2 = pivot low, click 3 = endpoint
 *   pitchfork.clear();    // Remove all pitchfork drawings
 *   pitchfork.isActive    // true while awaiting clicks
 *   pitchfork.drawings    // current drawings (persist to workspace)
 *
 * Andrews' Pitchfork:
 *   - Midpoint M = midpoint of point1 and point2
 *   - Median line: from M toward point3 direction, extended to last bar
 *   - Upper fork: from point1, parallel to median line
 *   - Lower fork: from point2, parallel to median line
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";

export interface PitchforkDrawing {
  id: string;
  point1: { time: number; price: number };
  point2: { time: number; price: number };
  point3: { time: number; price: number };
}

interface PitchforkTool {
  activate: () => void;
  deactivate: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  drawings: PitchforkDrawing[];
}

export function usePitchforkTool(
  chartRef: React.RefObject<IChartApi | null>,
  bars: BarData[],
  seriesRef: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): PitchforkTool {
  const [isActive, setIsActive] = useState(false);
  const [drawings, setDrawings] = useState<PitchforkDrawing[]>([]);

  // State machine: "idle" | "waiting_p1" | "waiting_p2" | "waiting_p3"
  const stateRef = useRef<"idle" | "waiting_p1" | "waiting_p2" | "waiting_p3">("idle");
  const p1Ref = useRef<{ time: number; price: number } | null>(null);
  const p2Ref = useRef<{ time: number; price: number } | null>(null);

  // Map drawing ID → [median, upper, lower] LineSeries
  const lineSeriesRef = useRef<Map<string, [ISeriesApi<"Line">, ISeriesApi<"Line">, ISeriesApi<"Line">]>>(new Map());

  const { LineSeries } = require("lightweight-charts") as typeof import("lightweight-charts");

  const getLastBarTime = useCallback((): number => {
    if (bars.length === 0) return Date.now() / 1000;
    return new Date(bars[bars.length - 1].time).getTime() / 1000;
  }, [bars]);

  /**
   * Build the three line segments for a pitchfork, extended to the last bar.
   * M = midpoint(p1, p2)
   * Direction vector from M to p3, extended to lastBarTime.
   * Upper/lower forks start from p1/p2 with the same slope.
   */
  const buildForkLines = useCallback(
    (
      p1: { time: number; price: number },
      p2: { time: number; price: number },
      p3: { time: number; price: number }
    ): {
      median: { time: number; price: number }[];
      upper: { time: number; price: number }[];
      lower: { time: number; price: number }[];
    } => {
      const lastT = getLastBarTime();

      // Midpoint of p1 and p2
      const mTime = (p1.time + p2.time) / 2;
      const mPrice = (p1.price + p2.price) / 2;

      // Slope of median line: (p3 - M) / dT
      const dT = p3.time - mTime;
      const dP = p3.price - mPrice;
      const slope = dT === 0 ? 0 : dP / dT;

      // Extend to last bar
      const medianEndPrice = mPrice + slope * (lastT - mTime);
      const upperEndPrice = p1.price + slope * (lastT - p1.time);
      const lowerEndPrice = p2.price + slope * (lastT - p2.time);

      return {
        median: [
          { time: mTime, price: mPrice },
          { time: lastT, price: medianEndPrice },
        ],
        upper: [
          { time: p1.time, price: p1.price },
          { time: lastT, price: upperEndPrice },
        ],
        lower: [
          { time: p2.time, price: p2.price },
          { time: lastT, price: lowerEndPrice },
        ],
      };
    },
    [getLastBarTime]
  );

  const drawPitchfork = useCallback(
    (
      p1: { time: number; price: number },
      p2: { time: number; price: number },
      p3: { time: number; price: number }
    ): PitchforkDrawing => {
      const id = `pitchfork-${Date.now()}`;
      const chart = chartRef.current;

      if (chart) {
        const { median, upper, lower } = buildForkLines(p1, p2, p3);

        const medianSeries = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 1,
          lineStyle: 0,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        medianSeries.setData(
          median.map(({ time, price }) => ({ time: time as Time, value: price }))
        );

        const upperSeries = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        upperSeries.setData(
          upper.map(({ time, price }) => ({ time: time as Time, value: price }))
        );

        const lowerSeries = chart.addSeries(LineSeries, {
          color: "#f59e0b",
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        lowerSeries.setData(
          lower.map(({ time, price }) => ({ time: time as Time, value: price }))
        );

        lineSeriesRef.current.set(id, [medianSeries, upperSeries, lowerSeries]);
      }

      return { id, point1: p1, point2: p2, point3: p3 };
    },
    [chartRef, buildForkLines, LineSeries]
  );

  const removePitchforkSeries = useCallback(
    (id: string) => {
      const chart = chartRef.current;
      const seriesTuple = lineSeriesRef.current.get(id);
      if (chart && seriesTuple) {
        for (const s of seriesTuple) {
          try {
            chart.removeSeries(s);
          } catch {
            // Series may already be gone
          }
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
      const series = seriesRef.current;
      if (!series) return;

      const price = series.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      const timeNum = typeof param.time === "number"
        ? param.time
        : (param.time as unknown as number);

      if (stateRef.current === "waiting_p1") {
        p1Ref.current = { time: timeNum, price };
        stateRef.current = "waiting_p2";
        return;
      }

      if (stateRef.current === "waiting_p2" && p1Ref.current !== null) {
        p2Ref.current = { time: timeNum, price };
        stateRef.current = "waiting_p3";
        return;
      }

      if (stateRef.current === "waiting_p3" && p1Ref.current !== null && p2Ref.current !== null) {
        const drawing = drawPitchfork(p1Ref.current, p2Ref.current, { time: timeNum, price });
        setDrawings((prev) => [...prev, drawing]);
        stateRef.current = "idle";
        p1Ref.current = null;
        p2Ref.current = null;
        setIsActive(false);
      }
    };

    chart.subscribeClick(handleClick);
    return () => chart.unsubscribeClick(handleClick);
  }, [isActive, chartRef, drawPitchfork, seriesRef]);

  const activate = useCallback(() => {
    stateRef.current = "waiting_p1";
    p1Ref.current = null;
    p2Ref.current = null;
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    stateRef.current = "idle";
    p1Ref.current = null;
    p2Ref.current = null;
    setIsActive(false);
  }, []);

  const clear = useCallback(() => {
    for (const id of lineSeriesRef.current.keys()) {
      removePitchforkSeries(id);
    }
    setDrawings([]);
  }, [removePitchforkSeries]);

  const removeDrawing = useCallback(
    (id: string) => {
      removePitchforkSeries(id);
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removePitchforkSeries]
  );

  return { activate, deactivate, clear, removeDrawing, isActive, drawings };
}
