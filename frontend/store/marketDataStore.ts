/**
 * Zustand store — real-time market data (quotes map).
 *
 * Receives updates from the single WebSocket connection in useWebSocket.
 * All panels subscribe to their symbol's slice — no duplicate connections.
 */
import { create } from "zustand";
import type { Quote } from "@/types/market";

interface MarketDataState {
  quotes: Record<string, Quote>;
  setQuote: (quote: Quote) => void;
  getQuote: (symbol: string) => Quote | undefined;
}

export const useMarketDataStore = create<MarketDataState>((set, get) => ({
  quotes: {},

  setQuote: (quote) =>
    set((state) => ({
      quotes: { ...state.quotes, [quote.symbol]: quote },
    })),

  getQuote: (symbol) => get().quotes[symbol],
}));
