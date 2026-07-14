/**
 * lib/api/screener.ts — Screener, Macro, Calendar, Crypto API helpers.
 */
import { apiRequest } from "./client";

// ─── Screener ─────────────────────────────────────────────────────────────────
export interface ScreenerCondition {
  field: string;
  op: string;
  value: string | number | boolean | [number, number];
}

export interface ScreenerPreset {
  id: string;
  name: string;
  description: string;
  conditions: ScreenerCondition[];
  logic: "AND" | "OR";
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  sector: string;
  market_cap: number | null;
  price: number | null;
  change_pct_1d: number | null;
  pe_ratio: number | null;
  volume_ratio: number | null;
  rsi_14: number | null;
}

export interface ScreenerResponse {
  results: ScreenerRow[];
  count: number;
  total_universe: number;
}

export interface SectorData {
  sector: string;
  symbols: string[];
  avg_change_pct: number;
  stocks: { symbol: string; name: string; change_pct_1d: number; market_cap: number }[];
}

export interface CorrelationData {
  symbols: string[];
  matrix: number[][];
  note?: string;
}

export async function runScreener(payload: {
  conditions: ScreenerCondition[];
  logic: "AND" | "OR";
  limit?: number;
  sort_by?: string;
  sort_desc?: boolean;
}): Promise<ScreenerResponse> {
  return apiRequest<ScreenerResponse>("/screener/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getScreenerPresets(): Promise<{ presets: ScreenerPreset[] }> {
  return apiRequest("/screener/presets");
}

export async function getSectorMap(): Promise<{ sectors: SectorData[] }> {
  return apiRequest("/screener/universe/sectors");
}

export async function getCorrelations(symbols: string[]): Promise<CorrelationData> {
  return apiRequest(`/screener/universe/correlations?symbols=${symbols.join(",")}`);
}

// ─── Alerts ───────────────────────────────────────────────────────────────────
export interface Alert {
  id: string;
  user_id: string;
  symbol: string | null;
  alert_type: string;
  threshold: number;
  label: string;
  status: "pending" | "triggered" | "acknowledged" | "expired";
  created_at: string;
  triggered_at: string | null;
}

export interface AlertType {
  value: string;
  label: string;
}

export async function listAlerts(): Promise<{ alerts: Alert[]; count: number }> {
  return apiRequest("/alerts");
}

export async function createAlert(payload: {
  symbol?: string;
  alert_type: string;
  threshold: number;
  label?: string;
}): Promise<Alert> {
  return apiRequest<Alert>("/alerts", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateAlert(
  id: string,
  payload: { threshold?: number; label?: string; rearm?: boolean }
): Promise<Alert> {
  return apiRequest<Alert>(`/alerts/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export async function deleteAlert(id: string): Promise<void> {
  return apiRequest<void>(`/alerts/${id}`, { method: "DELETE" });
}

export async function acknowledgeAlert(id: string): Promise<Alert> {
  return apiRequest<Alert>(`/alerts/${id}/acknowledge`, { method: "POST" });
}

export async function getAlertTypes(): Promise<{ types: AlertType[] }> {
  return apiRequest("/alerts/types");
}

// ─── Macro ────────────────────────────────────────────────────────────────────
export interface MacroIndicator {
  value: number | null;
  label: string;
  unit: string;
}

export interface YieldPoint {
  maturity: string;
  yield: number;
}

export interface MacroSnapshot extends Record<string, MacroIndicator | string> {
  as_of: string;
}

export async function getMacroIndicators(): Promise<MacroSnapshot> {
  return apiRequest<MacroSnapshot>("/macro/indicators");
}

export async function getYieldCurve(): Promise<{
  curve: YieldPoint[];
  inverted: boolean;
  as_of: string;
  note?: string;
}> {
  return apiRequest("/macro/yield-curve");
}

export async function getVix(): Promise<{
  value: number;
  regime: string;
  as_of: string;
}> {
  return apiRequest("/macro/vix");
}

// ─── Economic Calendar ────────────────────────────────────────────────────────
export interface CalendarEvent {
  id: string;
  date: string;
  time: string;
  currency: string;
  impact: "high" | "medium" | "low";
  event: string;
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  is_upcoming: boolean;
  days_until: number;
}

export async function getCalendarEvents(params?: {
  start?: string;
  end?: string;
  impact?: string;
}): Promise<{ events: CalendarEvent[]; count: number; as_of: string }> {
  const qs = new URLSearchParams();
  if (params?.start) qs.set("start", params.start);
  if (params?.end) qs.set("end", params.end);
  if (params?.impact) qs.set("impact", params.impact);
  return apiRequest(`/calendar/events${qs.toString() ? `?${qs}` : ""}`);
}

// ─── Crypto ───────────────────────────────────────────────────────────────────
export interface FundingRate {
  symbol: string;
  funding_rate: number;
  next_funding_time: string | null;
  mark_price: number;
}

export interface CryptoMover {
  symbol: string;
  name: string;
  price: number;
  change_24h: number | null;
  volume_24h: number | null;
  market_cap: number | null;
}

export async function getFundingRates(): Promise<{ rates: FundingRate[]; as_of: string }> {
  return apiRequest("/crypto/funding-rates");
}

export async function getCryptoTopMovers(limit = 10): Promise<{ movers: CryptoMover[]; as_of: string }> {
  return apiRequest(`/crypto/top-movers?limit=${limit}`);
}

export async function getCryptoOnchain(symbol: string): Promise<{
  symbol: string;
  metrics: Record<string, number | null>;
  as_of: string;
}> {
  return apiRequest(`/crypto/onchain/${symbol}`);
}
