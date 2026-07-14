/**
 * Zustand store — orders / fill notifications.
 *
 * PortfolioPanel subscribes to `lastFill` to trigger a position refresh
 * whenever an order is reported as filled via the WebSocket feed.
 */

import { create } from "zustand";

export interface OrderFill {
  orderId: string;
  symbol: string;
  side: string;
  filledQty: number;
  filledAvgPrice: number | null;
  filledAt: string;
}

interface OrdersState {
  /** The most recent fill event. PortfolioPanel watches this to refresh. */
  lastFill: OrderFill | null;
  setLastFill: (fill: OrderFill) => void;
  clearLastFill: () => void;
}

export const useOrdersStore = create<OrdersState>()((set) => ({
  lastFill: null,
  setLastFill: (fill) => set({ lastFill: fill }),
  clearLastFill: () => set({ lastFill: null }),
}));
