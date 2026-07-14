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
  options?: { start?: string; end?: string; limit?: number; chart_type?: string; brick_size?: number; n_lines?: number }
): Promise<BarsResponse> {
  const params = new URLSearchParams({ timeframe });
  if (options?.start) params.set("start", options.start);
  if (options?.end) params.set("end", options.end);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.chart_type) params.set("chart_type", options.chart_type);
  if (options?.brick_size != null) params.set("brick_size", String(options.brick_size));
  if (options?.n_lines != null) params.set("n_lines", String(options.n_lines));
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

export interface VPVRLevelData {
  price: number;
  volume: number;
  is_poc: boolean;
  pct_of_max: number;
}

export interface VPVRResponse {
  symbol: string;
  price_levels: VPVRLevelData[];
  poc: number | null;
}

export async function getVPVR(
  symbol: string,
  timeframe: string,
  options?: { start?: string; end?: string; bins?: number }
): Promise<VPVRResponse> {
  const params = new URLSearchParams({ timeframe });
  if (options?.start) params.set("start", options.start);
  if (options?.end) params.set("end", options.end);
  if (options?.bins) params.set("bins", String(options.bins));
  return apiRequest<VPVRResponse>(`/market/vpvr/${symbol}?${params}`);
}
