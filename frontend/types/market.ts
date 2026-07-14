/**
 * Market data TypeScript types — canonical shapes used throughout the app.
 * Must match the FastAPI Pydantic schemas.
 */

export type AssetClass = "equity" | "crypto" | "forex" | "futures" | "options";
export type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d" | "1w";
export type OrderSide = "B" | "S" | "U";

export interface Quote {
  symbol: string;
  price: number;
  bid?: number | null;
  ask?: number | null;
  bid_size?: number | null;
  ask_size?: number | null;
  volume?: number | null;
  change?: number | null;
  change_pct?: number | null;
  timestamp: string;
  provider?: string | null;
  asset_class?: string | null;
}

export interface OHLCVBar {
  time: number; // Unix seconds (TradingView Lightweight Charts format)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap?: number;
}

export interface Trade {
  symbol: string;
  price: number;
  size: number;
  side: OrderSide;
  exchange?: string;
  timestamp: string;
}

export interface OrderBookLevel {
  price: number;
  size: number;
}

export interface OrderBook {
  symbol: string;
  bids: [number, number][]; // [price, size]
  asks: [number, number][];
  timestamp: string;
}

export interface SymbolSearchResult {
  symbol: string;
  name: string;
  asset_class: AssetClass;
  exchange: string;
  currency: string;
}

// WebSocket message envelope
export type WSMessage =
  | { type: "quote" } & Quote
  | { type: "trade" } & Trade
  | { type: "orderbook" } & OrderBook
  | { type: "alert_triggered"; alert_id: string; symbol: string; message: string; timestamp: string };
