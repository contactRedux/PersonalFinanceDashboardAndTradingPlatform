"use client";

/**
 * MarketDataProvider — mounts the single WebSocket market feed for the session.
 *
 * Architecture:
 *   - ONE WebSocket per browser session (not per panel/component)
 *   - Subscribes to all symbols in the active watchlist
 *   - All panels read from marketDataStore (Zustand) — not from WebSocket directly
 *
 * Placement: wrap the dashboard page content (not the layout) so the connection
 * persists across panel renders.
 */

import React, { useEffect, useRef } from "react";
import { useWatchlistStore } from "@/store/watchlistStore";
import { useMarketDataStore } from "@/store/marketDataStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { WS_URLS } from "@/lib/api/websocket";
import type { Quote } from "@/types/market";

interface MarketDataProviderProps {
  children: React.ReactNode;
}

export function MarketDataProvider({ children }: MarketDataProviderProps) {
  const setQuote = useMarketDataStore((s) => s.setQuote);
  const watchlists = useWatchlistStore((s) => s.watchlists);
  const activeId = useWatchlistStore((s) => s.activeWatchlistId);
  const sendRef = useRef<((data: unknown) => void) | null>(null);
  const subscribedRef = useRef<Set<string>>(new Set());

  // All active symbols from all watchlists (union)
  const allSymbols = Array.from(
    new Set(watchlists.flatMap((w) => w.symbols))
  );

  const { send } = useWebSocket({
    url: WS_URLS.market(),
    onMessage: (data) => {
      const msg = data as { type?: string } & Partial<Quote>;
      if (msg.type === "quote" && msg.symbol) {
        setQuote(msg as Quote);
      }
    },
    onConnect: () => {
      // Re-subscribe to all symbols after reconnect
      if (allSymbols.length && sendRef.current) {
        sendRef.current({ action: "subscribe", symbols: allSymbols });
        allSymbols.forEach((s) => subscribedRef.current.add(s));
      }
    },
    reconnectDelay: 3000,
    maxReconnectAttempts: 20,
  });

  // Keep sendRef updated
  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  // Subscribe to newly added symbols
  useEffect(() => {
    const newSymbols = allSymbols.filter((s) => !subscribedRef.current.has(s));
    if (newSymbols.length && sendRef.current) {
      sendRef.current({ action: "subscribe", symbols: newSymbols });
      newSymbols.forEach((s) => subscribedRef.current.add(s));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allSymbols.join(","), activeId]);

  return <>{children}</>;
}
