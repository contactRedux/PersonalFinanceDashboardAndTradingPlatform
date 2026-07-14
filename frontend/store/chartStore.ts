/**
 * Zustand store — per-panel chart configuration.
 * symbol + timeframe + active indicators + drawings per panel.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Timeframe } from "@/types/market";
import type { FibDrawing } from "@/components/panels/ChartPanel/useFibonacciTool";
import type { TrendlineDrawing } from "@/components/panels/ChartPanel/useTrendlineTool";
import type { PitchforkDrawing } from "@/components/panels/ChartPanel/usePitchforkTool";
import type { AnnotationDrawing } from "@/components/panels/ChartPanel/useAnnotationTool";

export type ChartType = "candlestick" | "heikin_ashi" | "line" | "area" | "bar" | "baseline" | "renko" | "line_break";

export interface IndicatorConfig {
  id: string;
  type: string;
  params: Record<string, number | string | boolean>;
  visible: boolean;
}

export interface PanelDrawings {
  fib: FibDrawing[];
  trendline: TrendlineDrawing[];
  pitchfork: PitchforkDrawing[];
  annotations: AnnotationDrawing[];
}

export interface PanelChartConfig {
  symbol: string;
  timeframe: Timeframe;
  chartType: ChartType;
  indicators: IndicatorConfig[];
  /** Drawing tool results — persisted so workspace save/load can restore them. */
  drawings: PanelDrawings;
}

interface ChartState {
  panels: Record<string, PanelChartConfig>;
  setSymbol: (panelId: string, symbol: string) => void;
  setTimeframe: (panelId: string, timeframe: Timeframe) => void;
  setChartType: (panelId: string, chartType: ChartType) => void;
  addIndicator: (panelId: string, indicator: IndicatorConfig) => void;
  removeIndicator: (panelId: string, indicatorId: string) => void;
  toggleIndicator: (panelId: string, indicatorId: string) => void;
  setDrawings: (panelId: string, drawings: PanelDrawings) => void;
}

const defaultConfig = (): PanelChartConfig => ({
  symbol: "AAPL",
  timeframe: "1d",
  chartType: "candlestick",
  indicators: [],
  drawings: { fib: [], trendline: [], pitchfork: [], annotations: [] },
});

export const useChartStore = create<ChartState>()(
  persist(
    (set) => ({
      panels: { chart: defaultConfig() },

      setSymbol: (panelId, symbol) =>
        set((state) => ({
          panels: {
            ...state.panels,
            [panelId]: { ...(state.panels[panelId] ?? defaultConfig()), symbol },
          },
        })),

      setTimeframe: (panelId, timeframe) =>
        set((state) => ({
          panels: {
            ...state.panels,
            [panelId]: { ...(state.panels[panelId] ?? defaultConfig()), timeframe },
          },
        })),

      setChartType: (panelId, chartType) =>
        set((state) => ({
          panels: {
            ...state.panels,
            [panelId]: { ...(state.panels[panelId] ?? defaultConfig()), chartType },
          },
        })),

      addIndicator: (panelId, indicator) =>
        set((state) => {
          const panel = state.panels[panelId] ?? defaultConfig();
          return {
            panels: {
              ...state.panels,
              [panelId]: { ...panel, indicators: [...panel.indicators, indicator] },
            },
          };
        }),

      removeIndicator: (panelId, indicatorId) =>
        set((state) => {
          const panel = state.panels[panelId] ?? defaultConfig();
          return {
            panels: {
              ...state.panels,
              [panelId]: {
                ...panel,
                indicators: panel.indicators.filter((i) => i.id !== indicatorId),
              },
            },
          };
        }),

      toggleIndicator: (panelId, indicatorId) =>
        set((state) => {
          const panel = state.panels[panelId] ?? defaultConfig();
          return {
            panels: {
              ...state.panels,
              [panelId]: {
                ...panel,
                indicators: panel.indicators.map((i) =>
                  i.id === indicatorId ? { ...i, visible: !i.visible } : i
                ),
              },
            },
          };
        }),

      setDrawings: (panelId, drawings) =>
        set((state) => ({
          panels: {
            ...state.panels,
            [panelId]: {
              ...(state.panels[panelId] ?? defaultConfig()),
              drawings,
            },
          },
        })),
    }),
    { name: "quantnexus-chart-configs" }
  )
);
