"use client";

/**
 * Gann Fan drawing tool for lightweight-charts.
 *
 * Usage:
 *   const gannFan = useGannFanTool(chartRef, bars, seriesRef);
 *   gannFan.activate();  // Click 1 = pivot point, Click 2 = reference point (sets 1×1 scale)
 *   gannFan.clear();     // Remove all Gann Fan drawings
 *   gannFan.isActive     // true while awaiting clicks
 *   gannFan.drawings     // current drawings (persist to workspace)
 *
 * Gann Angles (from pivot point):
 *   The 1×1 angle is defined by click 2 (price per bar slope).
 *   Other angles are multiples/fractions of the 1×1 slope.
 *
 * Fan lines:
 *   1×8, 1×4, 1×3, 1×2, 1×1, 2×1, 3×1, 4×1, 8×1
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { LineSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";

export interface GannFanDrawing {
  id: string;
  /** Pivot point (click 1) */
  pivot: { time: number; price: number };
  /** Reference point (click 2) — defines the 1×1 slope */
  ref: { time: number; price: number };
}

interface GannFanTool {
  activate: () => void;
  deactivate: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  drawings: GannFanDrawing[];
}

/** Gann fan line specifications */
const GANN_LINES: { label: string; slope: number; color: string; width: number }[] = [
  { label: "1×8", slope: 1 / 8, color: "#ef4444", width: 1 },
  { label: "1×4", slope: 1 / 4, color: "#f97316", width: 1 },
  { label: "1×3", slope: 1 / 3, color: "#eab308", width: 1 },
  { label: "1×2", slope: 1 / 2, color: "#84cc16", width: 1 },
  { label: "1×1", slope: 1 / 1, color: "#00d084", width: 2 },
  { label: "2×1", slope: 2 / 1, color: "#0ea5e9", width: 1 },
  { label: "3×1", slope: 3 / 1, color: "#8b5cf6", width: 1 },
  { label: "4×1", slope: 4 / 1, color: "#ec4899", width: 1 },
  { label: "8×1", slope: 8 / 1, color: "#ef4444", width: 1 },
];

const LINE_EXTENSION_BARS = 200; // extend fan lines this many bars to the right

export function useGannFanTool(
  chartRef: React.RefObject<IChartApi | null>,
  bars: BarData[],
  seriesRef: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): GannFanTool {
  const [isActive, setIsActive] = useState(false);
  const [drawings, setDrawings] = useState<GannFanDrawing[]>([]);

  // State machine: "idle" | "waiting_pivot" | "waiting_ref"
  const stateRef = useRef<"idle" | "waiting_pivot" | "waiting_ref">("idle");
  const pivotRef = useRef<{ time: number; price: number } | null>(null);

  // Map drawing ID → array of line series for cleanup
  const lineSeriesRefs = useRef<Map<string, ISeriesApi<"Line">[]>>(new Map());

  const drawFanLines = useCallback(
    (
      pivot: { time: number; price: number },
      ref: { time: number; price: number }
    ): GannFanDrawing => {
      const id = `gann-${Date.now()}`;
      const chart = chartRef.current;
      if (!chart || bars.length === 0) {
        return { id, pivot, ref };
      }

      // 1×1 slope: price change per bar from pivot to ref
      const barDelta = ref.time - pivot.time;
      const priceDelta = ref.price - pivot.price;
      const slope1x1 = barDelta !== 0 ? priceDelta / barDelta : priceDelta;

      // Determine bars available for extension
      const lastBarTime = bars[bars.length - 1]?.time ?? pivot.time;
      const barsAfterPivot = bars.filter((b) => Number(b.time) >= pivot.time);
      const extension = Math.max(barsAfterPivot.length + LINE_EXTENSION_BARS, 100);

      const seriesForId: ISeriesApi<"Line">[] = [];

      for (const fan of GANN_LINES) {
        const fanSlope = slope1x1 * fan.slope;

        // Build line data points from pivot to extension
        const lineData: { time: Time; value: number }[] = [];

        // Use actual bar times from pivot onward
        const startBarIdx = bars.findIndex((b) => Number(b.time) >= pivot.time);
        const endBarIdx = Math.min(bars.length - 1, startBarIdx + extension);

        for (let i = Math.max(0, startBarIdx); i <= endBarIdx; i++) {
          const barTime = Number(bars[i].time);
          const barOffset = barTime - pivot.time;
          lineData.push({
            time: bars[i].time as Time,
            value: pivot.price + fanSlope * barOffset,
          });
        }

        if (lineData.length < 2) continue;

        try {
          const ls = chart.addSeries(LineSeries, {
            color: fan.color,
            lineWidth: fan.width,
            lineStyle: fan.label === "1×1" ? 0 : 2, // solid for 1×1, dashed for others
            priceLineVisible: false,
            lastValueVisible: true,
            title: fan.label,
          });
          ls.setData(lineData);
          seriesForId.push(ls);
        } catch {
          // Chart may have been destroyed
        }
      }

      lineSeriesRefs.current.set(id, seriesForId);
      return { id, pivot, ref };
    },
    [chartRef, bars]
  );

  const removeFanLines = useCallback(
    (id: string) => {
      const chart = chartRef.current;
      const series = lineSeriesRefs.current.get(id) ?? [];
      if (chart) {
        for (const ls of series) {
          try {
            chart.removeSeries(ls);
          } catch {
            // already removed
          }
        }
      }
      lineSeriesRefs.current.delete(id);
    },
    [chartRef]
  );

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isActive) return;

    const handleClick = (param: { point?: { x: number; y: number } }) => {
      if (!param.point) return;
      const series = seriesRef.current;
      if (!series) return;

      const price = series.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      // Find bar time from x coordinate
      const timeCoord = chart.timeScale().coordinateToTime(param.point.x);
      if (!timeCoord) return;
      const barTime = Number(timeCoord);

      if (stateRef.current === "waiting_pivot") {
        pivotRef.current = { time: barTime, price };
        stateRef.current = "waiting_ref";
        return;
      }

      if (stateRef.current === "waiting_ref" && pivotRef.current) {
        const ref = { time: barTime, price };
        const drawing = drawFanLines(pivotRef.current, ref);
        setDrawings((prev) => [...prev, drawing]);
        stateRef.current = "idle";
        pivotRef.current = null;
        setIsActive(false);
      }
    };

    chart.subscribeClick(handleClick);
    return () => {
      chart.unsubscribeClick(handleClick);
    };
  }, [isActive, chartRef, seriesRef, drawFanLines]);

  const activate = useCallback(() => {
    stateRef.current = "waiting_pivot";
    pivotRef.current = null;
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    stateRef.current = "idle";
    pivotRef.current = null;
    setIsActive(false);
  }, []);

  const clear = useCallback(() => {
    for (const id of lineSeriesRefs.current.keys()) {
      removeFanLines(id);
    }
    setDrawings([]);
  }, [removeFanLines]);

  const removeDrawing = useCallback(
    (id: string) => {
      removeFanLines(id);
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removeFanLines]
  );

  return { activate, deactivate, clear, removeDrawing, isActive, drawings };
}
