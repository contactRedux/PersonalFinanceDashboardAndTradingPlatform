/**
 * Generic WebSocket hook with automatic reconnection.
 *
 * Design: ONE instance of useWebSocket per connection type (market, tape, etc.).
 * All panels read from Zustand stores — never open their own connections.
 *
 * Reconnect strategy: exponential backoff with ±25% jitter.
 *   delay(n) = clamp(baseDelay × 2^n, baseDelay, 1600) × jitter(0.75–1.25)
 * After maxReconnectAttempts, the hook stops and calls onMaxRetriesExceeded.
 */
"use client";

import { useEffect, useRef, useCallback } from "react";

export interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  /** Base reconnect delay in ms. First retry = baseDelay, doubles each attempt up to 1600ms cap. Default 100. */
  baseDelay?: number;
  /** @deprecated use baseDelay. Accepted for backward compatibility — treated as baseDelay. */
  reconnectDelay?: number;
  maxReconnectAttempts?: number; // default 10
  /** Called after maxReconnectAttempts failed attempts. */
  onMaxRetriesExceeded?: () => void;
}

const MAX_DELAY_MS = 1600;

/** Exported for unit testing. */
export function backoffDelay(baseDelay: number, attempt: number): number {
  const raw = baseDelay * Math.pow(2, attempt);
  const clamped = Math.min(Math.max(raw, baseDelay), MAX_DELAY_MS);
  // ±25% jitter
  const jitter = 0.75 + Math.random() * 0.5;
  return Math.round(clamped * jitter);
}

export function useWebSocket({
  url,
  onMessage,
  onConnect,
  onDisconnect,
  baseDelay,
  reconnectDelay,
  maxReconnectAttempts = 10,
  onMaxRetriesExceeded,
}: UseWebSocketOptions) {
  // Support legacy `reconnectDelay` as an alias for `baseDelay`
  const effectiveBaseDelay = baseDelay ?? reconnectDelay ?? 100;

  const ws = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const shouldReconnect = useRef(true);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Stable refs for callbacks so WebSocket handlers don't capture stale closures
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onMaxRetriesRef = useRef(onMaxRetriesExceeded);

  // Keep callback refs up to date without triggering reconnect
  useEffect(() => { onMessageRef.current = onMessage; });
  useEffect(() => { onConnectRef.current = onConnect; });
  useEffect(() => { onDisconnectRef.current = onDisconnect; });
  useEffect(() => { onMaxRetriesRef.current = onMaxRetriesExceeded; });

  useEffect(() => {
    shouldReconnect.current = true;
    reconnectCount.current = 0;

    function doConnect() {
      if (ws.current?.readyState === WebSocket.OPEN) return;

      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        reconnectCount.current = 0;
        onConnectRef.current?.();
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          onMessageRef.current(data);
        } catch {
          // Malformed message — ignore silently
        }
      };

      ws.current.onclose = () => {
        onDisconnectRef.current?.();
        if (shouldReconnect.current) {
          if (reconnectCount.current < maxReconnectAttempts) {
            const delay = backoffDelay(effectiveBaseDelay, reconnectCount.current);
            reconnectCount.current++;
            reconnectTimer.current = setTimeout(doConnect, delay);
          } else {
            onMaxRetriesRef.current?.();
          }
        }
      };

      ws.current.onerror = () => {
        ws.current?.close();
      };
    }

    doConnect();

    return () => {
      shouldReconnect.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [url, maxReconnectAttempts, effectiveBaseDelay]);

  const send = useCallback((data: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
