/**
 * Zustand store — real-time market data (quotes map + price history for sparklines).
 *
 * Receives updates from the single WebSocket connection in useWebSocket.
 * All panels subscribe to their symbol's slice — no duplicate connections.
 */
import { create } from "zustand";
import type { Quote } from "@/types/market";

const PRICE_HISTORY_LENGTH = 20;

interface MarketDataState {
  quotes: Record<string, Quote>;
  /** Last 20 close prices per symbol, used for WatchlistPanel sparklines. */
  priceHistory: Record<string, number[]>;
  setQuote: (quote: Quote) => void;
  getQuote: (symbol: string) => Quote | undefined;
}

export const useMarketDataStore = create<MarketDataState>((set, get) => ({
  quotes: {},
  priceHistory: {},

  setQuote: (quote) =>
    set((state) => {
      const prev = state.priceHistory[quote.symbol] ?? [];
      const updated = [...prev, quote.price].slice(-PRICE_HISTORY_LENGTH);
      return {
        quotes: { ...state.quotes, [quote.symbol]: quote },
        priceHistory: { ...state.priceHistory, [quote.symbol]: updated },
      };
    }),

  getQuote: (symbol) => get().quotes[symbol],
}));
