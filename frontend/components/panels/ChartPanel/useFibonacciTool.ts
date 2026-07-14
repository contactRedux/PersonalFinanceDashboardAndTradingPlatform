"use client";

/**
 * Fibonacci Retracement drawing tool for lightweight-charts.
 *
 * Usage:
 *   const fib = useFibonacciTool(chartRef, seriesRef);
 *   fib.activate();   // Click 1 = swing high, click 2 = swing low → draw
 *   fib.clear();      // Remove all Fibonacci drawings
 *   fib.isActive      // true while awaiting clicks
 *   fib.drawings      // current drawings (persist to workspace)
 *
 * Fibonacci levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, IPriceLine } from "lightweight-charts";

export const FIB_LEVELS: { ratio: number; label: string; color: string }[] = [
  { ratio: 0.0, label: "0%", color: "#ef4444" },
  { ratio: 0.236, label: "23.6%", color: "#f97316" },
  { ratio: 0.382, label: "38.2%", color: "#eab308" },
  { ratio: 0.5, label: "50%", color: "#22c55e" },
  { ratio: 0.618, label: "61.8%", color: "#0ea5e9" },
  { ratio: 0.786, label: "78.6%", color: "#8b5cf6" },
  { ratio: 1.0, label: "100%", color: "#ef4444" },
];

export interface FibDrawing {
  id: string;
  high: number;
  low: number;
  levels: { ratio: number; price: number }[];
}

interface FibTool {
  activate: () => void;
  deactivate: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  drawings: FibDrawing[];
}

export function useFibonacciTool(
  chartRef: React.RefObject<IChartApi | null>,
  // The primary series reference is needed to attach price lines
  seriesRef: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): FibTool {
  const [isActive, setIsActive] = useState(false);
  const [drawings, setDrawings] = useState<FibDrawing[]>([]);

  // State machine: "idle" | "waiting_high" | "waiting_low"
  const stateRef = useRef<"idle" | "waiting_high" | "waiting_low">("idle");
  const firstPriceRef = useRef<number | null>(null);

  // Map drawing ID → array of IPriceLine references for cleanup
  const priceLineRefs = useRef<Map<string, IPriceLine[]>>(new Map());

  const drawFibLevels = useCallback(
    (high: number, low: number): FibDrawing => {
      const id = `fib-${Date.now()}`;
      const series = seriesRef.current;
      const priceLinesForThis: IPriceLine[] = [];

      const levelData = FIB_LEVELS.map(({ ratio, label, color }) => {
        const price = high - ratio * (high - low);
        if (series) {
          const pl = series.createPriceLine({
            price,
            color,
            lineWidth: 1,
            lineStyle: 2, // dashed
            axisLabelVisible: true,
            title: `Fib ${label}`,
          });
          priceLinesForThis.push(pl);
        }
        return { ratio, price };
      });

      priceLineRefs.current.set(id, priceLinesForThis);

      return { id, high, low, levels: levelData };
    },
    [seriesRef]
  );

  const removeFibPriceLines = useCallback(
    (id: string) => {
      const series = seriesRef.current;
      const lines = priceLineRefs.current.get(id) ?? [];
      if (series) {
        for (const pl of lines) {
          try {
            series.removePriceLine(pl);
          } catch {
            // Series may have been recreated
          }
        }
      }
      priceLineRefs.current.delete(id);
    },
    [seriesRef]
  );

  // Subscribe to chart click events when active
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isActive) return;

    const handleClick = (param: { point?: { x: number; y: number } }) => {
      if (!param.point) return;
      const series = seriesRef.current;
      if (!series) return;

      // Convert y-pixel coordinate to price via the series API (v5)
      const price = series.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      if (stateRef.current === "waiting_high") {
        firstPriceRef.current = price;
        stateRef.current = "waiting_low";
        return;
      }

      if (stateRef.current === "waiting_low" && firstPriceRef.current !== null) {
        const high = Math.max(firstPriceRef.current, price);
        const low = Math.min(firstPriceRef.current, price);
        const drawing = drawFibLevels(high, low);
        setDrawings((prev) => [...prev, drawing]);
        stateRef.current = "idle";
        firstPriceRef.current = null;
        setIsActive(false);
      }
    };

    chart.subscribeClick(handleClick);
    return () => {
      chart.unsubscribeClick(handleClick);
    };
  }, [isActive, chartRef, drawFibLevels]);

  const activate = useCallback(() => {
    stateRef.current = "waiting_high";
    firstPriceRef.current = null;
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    stateRef.current = "idle";
    firstPriceRef.current = null;
    setIsActive(false);
  }, []);

  const clear = useCallback(() => {
    for (const id of priceLineRefs.current.keys()) {
      removeFibPriceLines(id);
    }
    setDrawings([]);
  }, [removeFibPriceLines]);

  const removeDrawing = useCallback(
    (id: string) => {
      removeFibPriceLines(id);
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removeFibPriceLines]
  );

  return { activate, deactivate, clear, removeDrawing, isActive, drawings };
}
