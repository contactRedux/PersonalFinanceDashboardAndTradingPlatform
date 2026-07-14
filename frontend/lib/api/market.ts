/**
 * Market data API calls.
 */
import { apiRequest } from "./client";
import type { OHLCVBar, Quote, SymbolSearchResult } from "@/types/market";

export interface BarsParams {
  timeframe?: string;
  start?: string;
  end?: string;
  limit?: number;
}

export async function fetchBars(symbol: string, params: BarsParams = {}): Promise<OHLCVBar[]> {
  const qs = new URLSearchParams();
  if (params.timeframe) qs.set("timeframe", params.timeframe);
  if (params.start) qs.set("start", params.start);
  if (params.end) qs.set("end", params.end);
  if (params.limit) qs.set("limit", String(params.limit));
  const res = await apiRequest<{ bars: OHLCVBar[] }>(`/market/bars/${symbol}?${qs}`);
  return res.bars;
}

export async function fetchQuotes(symbols: string[]): Promise<Record<string, Quote | null>> {
  const res = await apiRequest<{ quotes: Record<string, Quote | null> }>(
    `/market/quotes?symbols=${symbols.join(",")}`
  );
  return res.quotes;
}

export async function searchSymbols(q: string): Promise<SymbolSearchResult[]> {
  const res = await apiRequest<{ results: SymbolSearchResult[] }>(
    `/market/search?q=${encodeURIComponent(q)}`
  );
  return res.results;
}
