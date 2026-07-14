/**
 * Zustand store — dashboard panel layout (persisted to localStorage).
 * Uses react-grid-layout's Layout format.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export const DEFAULT_PANELS = [
  "chart",
  "watchlist",
  "portfolio",
  "news",
  "tickerTape",
] as const;

export type PanelId = (typeof DEFAULT_PANELS)[number] | string;

export interface PanelConfig {
  id: PanelId;
  visible: boolean;
  title: string;
}

// react-grid-layout layout item shape
export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: "chart",       x: 2,  y: 0,  w: 7, h: 18, minW: 4, minH: 8 },
  { i: "watchlist",   x: 0,  y: 0,  w: 2, h: 18, minW: 2, minH: 6 },
  { i: "portfolio",   x: 9,  y: 0,  w: 3, h: 9,  minW: 2, minH: 4 },
  { i: "news",        x: 9,  y: 9,  w: 3, h: 9,  minW: 2, minH: 4 },
  { i: "risk",        x: 0,  y: 18, w: 4, h: 10, minW: 2, minH: 4 },
  { i: "orderbook",   x: 4,  y: 18, w: 4, h: 10, minW: 2, minH: 6 },
  { i: "tape",        x: 8,  y: 18, w: 4, h: 10, minW: 2, minH: 6 },
  { i: "options",     x: 0,  y: 28, w: 6, h: 12, minW: 4, minH: 6 },
  { i: "screener",    x: 6,  y: 28, w: 6, h: 12, minW: 4, minH: 6 },
  { i: "alerts",      x: 0,  y: 40, w: 4, h: 10, minW: 2, minH: 4 },
  { i: "macro",       x: 4,  y: 40, w: 4, h: 10, minW: 2, minH: 6 },
  { i: "calendar",    x: 8,  y: 40, w: 4, h: 10, minW: 2, minH: 6 },
  { i: "heatmap",     x: 0,  y: 50, w: 6, h: 12, minW: 4, minH: 6 },
  { i: "correlation", x: 6,  y: 50, w: 6, h: 12, minW: 4, minH: 6 },
  { i: "darkpool",    x: 0,  y: 62, w: 6, h: 10, minW: 4, minH: 6 },
  { i: "crypto",      x: 6,  y: 62, w: 6, h: 10, minW: 4, minH: 6 },
  { i: "performance", x: 0,  y: 72, w: 6, h: 14, minW: 4, minH: 8 },
  { i: "mtf",         x: 6,  y: 72, w: 6, h: 14, minW: 4, minH: 8 },
  { i: "order-entry", x: 0,  y: 86, w: 4, h: 14, minW: 3, minH: 8 },
  { i: "backtest",    x: 4,  y: 86, w: 8, h: 20, minW: 4, minH: 12 },
  { i: "volatility",        x: 0,  y: 106, w: 7,  h: 16, minW: 4, minH: 10 },
  { i: "journal",           x: 7,  y: 106, w: 5,  h: 16, minW: 3, minH: 8 },
  { i: "strategy-builder",  x: 0,  y: 122, w: 12, h: 22, minW: 6, minH: 14 },
];

interface LayoutState {
  layout: LayoutItem[];
  panels: PanelConfig[];
  activeWorkspaceId: string | null;
  setLayout: (layout: LayoutItem[]) => void;
  togglePanel: (id: PanelId) => void;
  resetLayout: () => void;
  setActiveWorkspaceId: (id: string | null) => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      layout: DEFAULT_LAYOUT,
      panels: [
        { id: "chart",     visible: true, title: "Chart" },
        { id: "watchlist", visible: true, title: "Watchlist" },
        { id: "portfolio", visible: true, title: "Portfolio" },
        { id: "news",      visible: true, title: "News & Sentiment" },
      ],
      activeWorkspaceId: null,

      setLayout: (layout) => set({ layout }),

      togglePanel: (id) =>
        set((state) => ({
          panels: state.panels.map((p) =>
            p.id === id ? { ...p, visible: !p.visible } : p
          ),
        })),

      resetLayout: () => set({ layout: DEFAULT_LAYOUT }),

      setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),
    }),
    { name: "quantnexus-layout" }
  )
);
