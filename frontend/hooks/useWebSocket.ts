/**
 * Generic WebSocket hook with automatic reconnection.
 *
 * Design: ONE instance of useWebSocket per connection type (market, tape, etc.).
 * All panels read from Zustand stores — never open their own connections.
 */
"use client";

import { useEffect, useRef, useCallback } from "react";

export interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnectDelay?: number; // ms, default 3000
  maxReconnectAttempts?: number; // default 10
}

export function useWebSocket({
  url,
  onMessage,
  onConnect,
  onDisconnect,
  reconnectDelay = 3000,
  maxReconnectAttempts = 10,
}: UseWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const shouldReconnect = useRef(true);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Stable refs for callbacks so WebSocket handlers don't capture stale closures
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);

  // Keep callback refs up to date without triggering reconnect
  useEffect(() => { onMessageRef.current = onMessage; });
  useEffect(() => { onConnectRef.current = onConnect; });
  useEffect(() => { onDisconnectRef.current = onDisconnect; });

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
        if (shouldReconnect.current && reconnectCount.current < maxReconnectAttempts) {
          reconnectCount.current++;
          reconnectTimer.current = setTimeout(doConnect, reconnectDelay);
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
  }, [url, maxReconnectAttempts, reconnectDelay]);

  const send = useCallback((data: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
