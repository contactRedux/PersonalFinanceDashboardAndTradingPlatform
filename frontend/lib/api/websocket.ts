/**
 * WebSocket URL builders — generates ws:// or wss:// URLs for each feed.
 * Always appends the access token as a query parameter.
 */
import { getAccessToken } from "./client";

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ??
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`
    : "ws://localhost:8000");

function buildWsUrl(path: string): string {
  const token = getAccessToken();
  const url = `${WS_BASE}${path}`;
  return token ? `${url}?token=${encodeURIComponent(token)}` : url;
}

export const WS_URLS = {
  market: () => buildWsUrl("/ws/market"),
  tape: () => buildWsUrl("/ws/tape"),
  orderbook: (symbol: string) =>
    buildWsUrl(`/ws/orderbook/${encodeURIComponent(symbol)}`),
  alerts: () => buildWsUrl("/ws/alerts"),
};
