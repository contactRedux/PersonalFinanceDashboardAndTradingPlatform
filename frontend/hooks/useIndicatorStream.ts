/**
 * useIndicatorStream — subscribes to the SSE indicator streaming endpoint.
 *
 * Creates an EventSource for GET /market/indicators/stream/{symbol}?indicators=...
 * Parses incoming events and returns latest indicator values.
 * Cleans up on unmount or when symbol/indicators change.
 * Handles connection errors gracefully (sets connected: false).
 */
import { useEffect, useRef, useState } from "react";

export interface IndicatorStreamResult {
  values: Record<string, number>;
  connected: boolean;
}

export function useIndicatorStream(
  symbol: string,
  indicators: string[]
): IndicatorStreamResult {
  const [values, setValues] = useState<Record<string, number>>({});
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!symbol || indicators.length === 0) return;

    const params = new URLSearchParams({
      indicators: indicators.join(","),
    });

    // EventSource uses the browser's native SSE with cookies for auth
    // For non-browser environments (tests), guard with typeof check
    if (typeof EventSource === "undefined") return;

    const url = `/api/v1/market/indicators/stream/${encodeURIComponent(symbol)}?${params}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as {
          type?: string;
          values?: Record<string, number>;
        };
        if (data.type === "keepalive") return;
        if (data.values) {
          setValues((prev) => ({ ...prev, ...data.values }));
        }
      } catch {
        // Ignore malformed events
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [symbol, indicators.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return { values, connected };
}
