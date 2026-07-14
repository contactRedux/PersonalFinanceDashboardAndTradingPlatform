/**
 * Portfolio and position TypeScript types.
 */

export interface Portfolio {
  id: string;
  name: string;
  initial_capital: number;
  currency: string;
  equity: number;
  cash: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  max_drawdown: number;
}

export interface Position {
  id: string;
  symbol: string;
  asset_class: string;
  side: "long" | "short";
  quantity: number;
  avg_entry_price: number;
  current_price?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  stop_loss?: number;
  take_profit?: number;
  opened_at: string;
}

export interface RiskMetrics {
  var_95: number | null;
  var_99: number | null;
  cvar_95: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  calmar_ratio: number | null;
  beta: number | null;
  alpha: number | null;
  max_drawdown: number | null;
}
