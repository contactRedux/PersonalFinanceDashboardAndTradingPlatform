/**
 * Portfolio REST API helpers.
 */
import { apiRequest } from "./client";

export interface PortfolioSummary {
  user_id: string;
  equity: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  day_pnl: number;
  day_pnl_pct: number;
  buying_power: number;
  margin_used: number;
  currency: string;
  as_of: string;
}

export interface PositionData {
  symbol: string;
  asset_class: string;
  side: "long" | "short";
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  stop_loss?: number;
  take_profit?: number;
}

export interface PositionsResponse {
  positions: PositionData[];
}

export interface RiskMetricsResponse {
  var_95: number;
  cvar_95: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  max_drawdown_duration_days: number;
  beta: number;
  alpha: number;
  note?: string;
}

export interface KellyResult {
  kelly_fraction: number;
  half_kelly: number;
  position_size_usd: number;
  position_size_pct: number;
}

export async function getPortfolio(): Promise<PortfolioSummary> {
  return apiRequest<PortfolioSummary>("/portfolio");
}

export async function getPositions(): Promise<PositionsResponse> {
  return apiRequest<PositionsResponse>("/portfolio/positions");
}

export async function getRiskMetrics(): Promise<RiskMetricsResponse> {
  return apiRequest<RiskMetricsResponse>("/portfolio/risk");
}
