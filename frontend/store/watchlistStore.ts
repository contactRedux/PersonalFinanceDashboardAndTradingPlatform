/**
 * Zustand store — watchlists (persisted to localStorage).
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Watchlist {
  id: string;
  name: string;
  symbols: string[];
  isDefault: boolean;
}

interface WatchlistState {
  watchlists: Watchlist[];
  activeWatchlistId: string | null;
  addWatchlist: (name: string) => void;
  removeWatchlist: (id: string) => void;
  addSymbol: (watchlistId: string, symbol: string) => void;
  removeSymbol: (watchlistId: string, symbol: string) => void;
  setActive: (id: string) => void;
  getActive: () => Watchlist | undefined;
}

let idCounter = 0;

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      watchlists: [
        { id: "default", name: "My Watchlist", symbols: ["AAPL", "MSFT", "BTC-USD", "EUR-USD"], isDefault: true },
      ],
      activeWatchlistId: "default",

      addWatchlist: (name) =>
        set((state) => ({
          watchlists: [
            ...state.watchlists,
            { id: `wl-${++idCounter}`, name, symbols: [], isDefault: false },
          ],
        })),

      removeWatchlist: (id) =>
        set((state) => ({
          watchlists: state.watchlists.filter((w) => w.id !== id),
        })),

      addSymbol: (watchlistId, symbol) =>
        set((state) => ({
          watchlists: state.watchlists.map((w) =>
            w.id === watchlistId && !w.symbols.includes(symbol.toUpperCase())
              ? { ...w, symbols: [...w.symbols, symbol.toUpperCase()] }
              : w
          ),
        })),

      removeSymbol: (watchlistId, symbol) =>
        set((state) => ({
          watchlists: state.watchlists.map((w) =>
            w.id === watchlistId
              ? { ...w, symbols: w.symbols.filter((s) => s !== symbol) }
              : w
          ),
        })),

      setActive: (id) => set({ activeWatchlistId: id }),

      getActive: () => {
        const { watchlists, activeWatchlistId } = get();
        return watchlists.find((w) => w.id === activeWatchlistId);
      },
    }),
    { name: "quantnexus-watchlists" }
  )
);
