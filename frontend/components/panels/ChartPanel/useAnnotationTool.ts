"use client";

/**
 * Annotation (price-level label) drawing tool for lightweight-charts.
 *
 * Usage:
 *   const annotation = useAnnotationTool(chartRef, seriesRef);
 *   annotation.activate();  // single click → prompts for text → places price line
 *   annotation.clear();     // remove all annotations
 *   annotation.isActive     // true while awaiting a click
 *   annotation.drawings     // current annotations (persist to workspace)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, IPriceLine, Time } from "lightweight-charts";

export interface AnnotationDrawing {
  id: string;
  price: number;
  label: string;
}

interface AnnotationTool {
  activate: () => void;
  deactivate: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  drawings: AnnotationDrawing[];
}

export function useAnnotationTool(
  chartRef: React.RefObject<IChartApi | null>,
  seriesRef: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): AnnotationTool {
  const [isActive, setIsActive] = useState(false);
  const [drawings, setDrawings] = useState<AnnotationDrawing[]>([]);

  // Map drawing ID → IPriceLine for cleanup
  const priceLineRefs = useRef<Map<string, IPriceLine>>(new Map());

  const addAnnotation = useCallback(
    (price: number, label: string): AnnotationDrawing => {
      const id = `annotation-${Date.now()}`;
      const series = seriesRef.current;

      if (series) {
        const pl = series.createPriceLine({
          price,
          color: "#f59e0b",
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: true,
          title: label,
        });
        priceLineRefs.current.set(id, pl);
      }

      return { id, price, label };
    },
    [seriesRef]
  );

  const removeAnnotationPriceLine = useCallback(
    (id: string) => {
      const series = seriesRef.current;
      const pl = priceLineRefs.current.get(id);
      if (series && pl) {
        try {
          series.removePriceLine(pl);
        } catch {
          // Series may have been recreated
        }
      }
      priceLineRefs.current.delete(id);
    },
    [seriesRef]
  );

  // Subscribe to click events when active
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isActive) return;

    const handleClick = (param: { point?: { x: number; y: number }; time?: Time }) => {
      if (!param.point) return;
      const series = seriesRef.current;
      if (!series) return;

      const price = series.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      const labelText = window.prompt("Annotation text:", "");
      if (labelText === null) {
        // User cancelled — no annotation placed
        return;
      }

      const drawing = addAnnotation(price, labelText);
      setDrawings((prev) => [...prev, drawing]);
      setIsActive(false);
    };

    chart.subscribeClick(handleClick);
    return () => chart.unsubscribeClick(handleClick);
  }, [isActive, chartRef, seriesRef, addAnnotation]);

  const activate = useCallback(() => {
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    setIsActive(false);
  }, []);

  const clear = useCallback(() => {
    for (const id of priceLineRefs.current.keys()) {
      removeAnnotationPriceLine(id);
    }
    setDrawings([]);
  }, [removeAnnotationPriceLine]);

  const removeDrawing = useCallback(
    (id: string) => {
      removeAnnotationPriceLine(id);
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removeAnnotationPriceLine]
  );

  return { activate, deactivate, clear, removeDrawing, isActive, drawings };
}
