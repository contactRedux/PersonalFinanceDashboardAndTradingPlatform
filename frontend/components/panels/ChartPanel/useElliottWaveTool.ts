"use client";

/**
 * Elliott Wave manual labeling tool for lightweight-charts.
 *
 * Usage:
 *   const wave = useElliottWaveTool(chartRef, bars, seriesRef);
 *   wave.activate("impulse");   // Starts the 1→2→3→4→5 labeling sequence
 *   wave.activate("corrective"); // Starts the A→B→C labeling sequence
 *   wave.finishWave();          // End the current wave count (also triggered by double-click or Escape)
 *   wave.clear();               // Remove all wave drawings
 *
 * Interaction:
 *   - Each single click places the NEXT label in the sequence at that price + bar
 *   - Lines connect consecutive pivot points
 *   - Double-click or pressing Escape ends the current wave count
 *   - Labels are rendered as price-line titles on the series
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { LineSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, IPriceLine, Time } from "lightweight-charts";
import type { BarData } from "@/lib/api/market";

// ─── Wave label sequences ─────────────────────────────────────────────────

const IMPULSE_LABELS = ["1", "2", "3", "4", "5"] as const;
const CORRECTIVE_LABELS = ["A", "B", "C"] as const;

export type WaveMode = "impulse" | "corrective";
export type WaveLabel = typeof IMPULSE_LABELS[number] | typeof CORRECTIVE_LABELS[number];

export interface WavePivot {
  label: WaveLabel;
  time: number;
  price: number;
}

export interface ElliottWaveDrawing {
  id: string;
  mode: WaveMode;
  pivots: WavePivot[];
  /** Whether the wave count is complete */
  complete: boolean;
}

interface ElliottWaveTool {
  activate: (mode: WaveMode) => void;
  deactivate: () => void;
  finishWave: () => void;
  clear: () => void;
  removeDrawing: (id: string) => void;
  isActive: boolean;
  mode: WaveMode;
  drawings: ElliottWaveDrawing[];
}

/** Colors for each wave label */
const WAVE_COLORS: Record<string, string> = {
  "1": "#00d084",
  "2": "#ef4444",
  "3": "#00d084",
  "4": "#ef4444",
  "5": "#00d084",
  "A": "#f59e0b",
  "B": "#f59e0b",
  "C": "#f59e0b",
};

export function useElliottWaveTool(
  chartRef: React.RefObject<IChartApi | null>,
  bars: BarData[],
  seriesRef: React.RefObject<ISeriesApi<"Candlestick" | "Line" | "Area" | "Bar" | "Baseline"> | null>
): ElliottWaveTool {
  const [isActive, setIsActive] = useState(false);
  const [mode, setMode] = useState<WaveMode>("impulse");
  const [drawings, setDrawings] = useState<ElliottWaveDrawing[]>([]);

  // Current wave being built
  const currentWaveRef = useRef<ElliottWaveDrawing | null>(null);
  const lastClickTimeRef = useRef<number>(0);

  // Map drawing ID → { priceLines, lineSeries }
  const renderRefs = useRef<
    Map<string, { priceLines: IPriceLine[]; lineSeries: ISeriesApi<"Line">[] }>
  >(new Map());

  const getLabels = useCallback((waveMode: WaveMode): readonly WaveLabel[] => {
    return waveMode === "impulse" ? IMPULSE_LABELS : CORRECTIVE_LABELS;
  }, []);

  const addPivotToChart = useCallback(
    (id: string, pivot: WavePivot, prevPivot: WavePivot | null) => {
      const chart = chartRef.current;
      const series = seriesRef.current;
      if (!chart || !series) return;

      const existing = renderRefs.current.get(id) ?? { priceLines: [], lineSeries: [] };

      // Add a price-line label at the pivot price
      const color = WAVE_COLORS[pivot.label] ?? "#aaa";
      const pl = series.createPriceLine({
        price: pivot.price,
        color,
        lineWidth: 1,
        lineStyle: 2, // dashed
        axisLabelVisible: true,
        title: `W${pivot.label}`,
      });
      existing.priceLines.push(pl);

      // Draw a line from the previous pivot to this one
      if (prevPivot) {
        try {
          // Find bar entries for these timestamps
          const prevBarEntry = bars.find((b) => Number(b.time) >= prevPivot.time);
          const thisBarEntry = bars.find((b) => Number(b.time) >= pivot.time);

          if (prevBarEntry && thisBarEntry) {
            const ls = chart.addSeries(LineSeries, {
              color,
              lineWidth: 1.5,
              lineStyle: 0,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            ls.setData([
              { time: prevBarEntry.time as Time, value: prevPivot.price },
              { time: thisBarEntry.time as Time, value: pivot.price },
            ]);
            existing.lineSeries.push(ls);
          }
        } catch {
          // Chart may have been remounted
        }
      }

      renderRefs.current.set(id, existing);
    },
    [chartRef, seriesRef, bars]
  );

  const removeDrawingFromChart = useCallback(
    (id: string) => {
      const chart = chartRef.current;
      const series = seriesRef.current;
      const refs = renderRefs.current.get(id);
      if (!refs) return;

      if (series) {
        for (const pl of refs.priceLines) {
          try { series.removePriceLine(pl); } catch { /* noop */ }
        }
      }
      if (chart) {
        for (const ls of refs.lineSeries) {
          try { chart.removeSeries(ls); } catch { /* noop */ }
        }
      }
      renderRefs.current.delete(id);
    },
    [chartRef, seriesRef]
  );

  const finishWave = useCallback(() => {
    const wave = currentWaveRef.current;
    if (!wave) return;

    // Mark current wave as complete and commit to drawings
    const finalWave: ElliottWaveDrawing = { ...wave, complete: true };
    setDrawings((prev) =>
      prev.map((d) => (d.id === wave.id ? finalWave : d))
    );
    currentWaveRef.current = null;
    setIsActive(false);
  }, []);

  // Keyboard handler for Escape
  useEffect(() => {
    if (!isActive) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        finishWave();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isActive, finishWave]);

  // Click handler
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isActive) return;

    const handleClick = (param: { point?: { x: number; y: number } }) => {
      if (!param.point) return;
      const series = seriesRef.current;
      if (!series) return;

      // Detect double-click (two clicks within 400ms)
      const now = Date.now();
      const isDoubleClick = now - lastClickTimeRef.current < 400;
      lastClickTimeRef.current = now;

      if (isDoubleClick) {
        finishWave();
        return;
      }

      const price = series.coordinateToPrice(param.point.y);
      if (price === null || price === undefined) return;

      const timeCoord = chart.timeScale().coordinateToTime(param.point.x);
      if (!timeCoord) return;
      const barTime = Number(timeCoord);

      const labels = getLabels(mode);
      let wave = currentWaveRef.current;

      if (!wave) {
        // Start a new wave sequence
        const id = `wave-${Date.now()}`;
        wave = { id, mode, pivots: [], complete: false };
        currentWaveRef.current = wave;
        setDrawings((prev) => [...prev, wave!]);
      }

      const nextIdx = wave.pivots.length;
      if (nextIdx >= labels.length) {
        // Sequence complete
        finishWave();
        return;
      }

      const pivot: WavePivot = {
        label: labels[nextIdx],
        time: barTime,
        price,
      };

      const prevPivot = wave.pivots[wave.pivots.length - 1] ?? null;
      wave.pivots = [...wave.pivots, pivot];
      currentWaveRef.current = wave;

      // Update state
      setDrawings((prev) =>
        prev.map((d) => (d.id === wave!.id ? { ...wave! } : d))
      );

      addPivotToChart(wave.id, pivot, prevPivot);

      // Auto-finish when all labels placed
      if (wave.pivots.length === labels.length) {
        finishWave();
      }
    };

    chart.subscribeClick(handleClick);
    return () => {
      chart.unsubscribeClick(handleClick);
    };
  }, [isActive, mode, chartRef, seriesRef, getLabels, finishWave, addPivotToChart]);

  const activate = useCallback((waveMode: WaveMode = "impulse") => {
    currentWaveRef.current = null;
    lastClickTimeRef.current = 0;
    setMode(waveMode);
    setIsActive(true);
  }, []);

  const deactivate = useCallback(() => {
    finishWave();
  }, [finishWave]);

  const clear = useCallback(() => {
    for (const id of renderRefs.current.keys()) {
      removeDrawingFromChart(id);
    }
    currentWaveRef.current = null;
    setDrawings([]);
    setIsActive(false);
  }, [removeDrawingFromChart]);

  const removeDrawing = useCallback(
    (id: string) => {
      removeDrawingFromChart(id);
      if (currentWaveRef.current?.id === id) {
        currentWaveRef.current = null;
        setIsActive(false);
      }
      setDrawings((prev) => prev.filter((d) => d.id !== id));
    },
    [removeDrawingFromChart]
  );

  return {
    activate,
    deactivate,
    finishWave,
    clear,
    removeDrawing,
    isActive,
    mode,
    drawings,
  };
}
