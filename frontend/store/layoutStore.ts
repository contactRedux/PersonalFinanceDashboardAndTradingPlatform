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
  { i: "chart",     x: 2, y: 0, w: 7, h: 18, minW: 4, minH: 8 },
  { i: "watchlist", x: 0, y: 0, w: 2, h: 18, minW: 2, minH: 6 },
  { i: "portfolio", x: 9, y: 0, w: 3, h: 9,  minW: 2, minH: 4 },
  { i: "news",      x: 9, y: 9, w: 3, h: 9,  minW: 2, minH: 4 },
];

interface LayoutState {
  layout: LayoutItem[];
  panels: PanelConfig[];
  setLayout: (layout: LayoutItem[]) => void;
  togglePanel: (id: PanelId) => void;
  resetLayout: () => void;
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

      setLayout: (layout) => set({ layout }),

      togglePanel: (id) =>
        set((state) => ({
          panels: state.panels.map((p) =>
            p.id === id ? { ...p, visible: !p.visible } : p
          ),
        })),

      resetLayout: () => set({ layout: DEFAULT_LAYOUT }),
    }),
    { name: "quantnexus-layout" }
  )
);
