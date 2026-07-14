/**
 * WebSocket URL builder.
 * Uses the WS URL from environment or defaults to ws://localhost:8000.
 */

function getWsBase(): string {
  const base = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
  return base;
}

export function marketFeedUrl(token: string): string {
  return `${getWsBase()}/ws/market?token=${encodeURIComponent(token)}`;
}

export function tapeFeedUrl(token: string): string {
  return `${getWsBase()}/ws/tape?token=${encodeURIComponent(token)}`;
}

export function orderbookFeedUrl(symbol: string, token: string): string {
  return `${getWsBase()}/ws/orderbook/${symbol}?token=${encodeURIComponent(token)}`;
}

export function alertsFeedUrl(token: string): string {
  return `${getWsBase()}/ws/alerts?token=${encodeURIComponent(token)}`;
}
