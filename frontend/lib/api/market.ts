/**
 * Market data API functions — REST endpoints.
 */
import { apiRequest } from "./client";

export interface QuoteData {
  symbol: string;
  price: number | null;
  bid: number | null;
  ask: number | null;
  volume: number | null;
  change: number | null;
  change_pct: number | null;
  timestamp: string | null;
  provider: string | null;
  asset_class: string | null;
}

export interface BarData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
}

export interface BarsResponse {
  symbol: string;
  timeframe: string;
  bars: BarData[];
  count: number;
}

export interface SymbolSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  asset_class: string;
}

export async function getQuotes(
  symbols: string[]
): Promise<Record<string, QuoteData | null>> {
  const result = await apiRequest<{ quotes: Record<string, QuoteData | null> }>(
    `/market/quotes?symbols=${symbols.join(",")}`
  );
  return result.quotes;
}

export async function getBars(
  symbol: string,
  timeframe: string,
  options?: { start?: string; end?: string; limit?: number }
): Promise<BarsResponse> {
  const params = new URLSearchParams({ timeframe });
  if (options?.start) params.set("start", options.start);
  if (options?.end) params.set("end", options.end);
  if (options?.limit) params.set("limit", String(options.limit));
  return apiRequest<BarsResponse>(`/market/bars/${symbol}?${params}`);
}

export async function searchSymbols(
  query: string,
  assetClass?: string
): Promise<{ results: SymbolSearchResult[]; count: number }> {
  const params = new URLSearchParams({ q: query });
  if (assetClass) params.set("asset_class", assetClass);
  return apiRequest<{ results: SymbolSearchResult[]; count: number }>(
    `/market/search?${params}`
  );
}

export async function getSnapshot(
  symbol: string
): Promise<{ symbol: string; quote: QuoteData | null; timestamp: string }> {
  return apiRequest(`/market/snapshot/${symbol}`);
}
