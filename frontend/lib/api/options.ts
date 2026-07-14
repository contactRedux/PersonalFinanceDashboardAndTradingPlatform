/**
 * Options chain REST API helpers.
 */
import { apiRequest } from "./client";

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  theoretical_price: number;
}

export interface OptionContract {
  ticker: string;
  strike: number;
  expiry: string;
  contract_type: "call" | "put";
  greeks: Greeks;
  bid?: number;
  ask?: number;
  last?: number;
  volume?: number;
  open_interest?: number;
  iv?: number;
}

export interface OptionsChainResponse {
  symbol: string;
  expiry: string | null;
  underlying_price: number | null;
  chain: OptionContract[];
  expirations: string[];
  timestamp: string;
}

export interface ExpirationsResponse {
  symbol: string;
  expirations: string[];
}

export interface UnusualActivityResponse {
  activity: UnusualActivity[];
  note?: string;
}

export interface UnusualActivity {
  symbol: string;
  contract_type: "call" | "put";
  strike: number;
  expiry: string;
  premium: number;
  volume: number;
  open_interest: number;
  timestamp: string;
}

export async function getOptionsChain(
  symbol: string,
  expiry?: string
): Promise<OptionsChainResponse> {
  const params = expiry ? `?expiry=${encodeURIComponent(expiry)}` : "";
  return apiRequest<OptionsChainResponse>(`/options/chain/${symbol}${params}`);
}

export async function getExpirations(symbol: string): Promise<ExpirationsResponse> {
  return apiRequest<ExpirationsResponse>(`/options/expirations/${symbol}`);
}

export async function getUnusualActivity(
  symbol?: string,
  minPremium?: number
): Promise<UnusualActivityResponse> {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (minPremium != null) params.set("min_premium", String(minPremium));
  const qs = params.toString();
  return apiRequest<UnusualActivityResponse>(`/options/unusual-activity${qs ? `?${qs}` : ""}`);
}
