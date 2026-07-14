/**
 * useMarketData — manages the single market WebSocket connection.
 *
 * Architecture:
 *   - ONE WebSocket connection to /ws/market per browser session
 *   - Subscriptions are managed as a ref-based set
 *   - All incoming quote updates → marketDataStore
 *   - Components never open their own WebSocket connections
 *
 * Usage:
 *   const { subscribe, unsubscribe } = useMarketData();
 *   subscribe(["AAPL", "BTC-USD"]);
 */
"use client";

import { useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./useWebSocket";
import { useMarketDataStore } from "@/store/marketDataStore";
import { WS_URLS } from "@/lib/api/websocket";
import type { Quote } from "@/types/market";

export function useMarketData() {
  const setQuote = useMarketDataStore((s) => s.setQuote);
  const subscribed = useRef<Set<string>>(new Set());
  const sendRef = useRef<((data: unknown) => void) | null>(null);

  const handleMessage = useCallback(
    (data: unknown) => {
      const msg = data as Partial<Quote> & { type?: string; symbol?: string };
      if (msg.type === "quote" && msg.symbol) {
        setQuote(msg as Quote);
      }
    },
    [setQuote]
  );

  const { send } = useWebSocket({
    url: WS_URLS.market(),
    onMessage: handleMessage,
    reconnectDelay: 3000,
    maxReconnectAttempts: 20,
  });

  // Store send in a ref so subscribe/unsubscribe can use it without stale closure
  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const subscribe = useCallback((symbols: string[]) => {
    const newSymbols = symbols.filter((s) => !subscribed.current.has(s));
    if (!newSymbols.length) return;
    newSymbols.forEach((s) => subscribed.current.add(s));
    sendRef.current?.({ action: "subscribe", symbols: newSymbols });
  }, []);

  const unsubscribe = useCallback((symbols: string[]) => {
    const toRemove = symbols.filter((s) => subscribed.current.has(s));
    if (!toRemove.length) return;
    toRemove.forEach((s) => subscribed.current.delete(s));
    sendRef.current?.({ action: "unsubscribe", symbols: toRemove });
  }, []);

  return { subscribe, unsubscribe, send };
}
