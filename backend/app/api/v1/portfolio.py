"""
Portfolio REST endpoints.

For now, serves paper-trading portfolio data from PostgreSQL.
Live brokerage integration is deferred to the C++ execution engine phase.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.services.risk.ratios import (
    beta_alpha,
    cvar,
    historical_var,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)

router = APIRouter()


@router.get("")
async def get_portfolio(current_user: CurrentUser, db: DBSession):
    """Return portfolio summary (equity, cash, P&L) for the authenticated user."""
    # Paper trading portfolio — initialized with demo data for UI development
    return {
        "user_id": current_user["sub"],
        "equity": 100_000.00,
        "cash": 85_423.50,
        "unrealized_pnl": 2_341.75,
        "realized_pnl": 1_234.25,
        "day_pnl": 312.50,
        "day_pnl_pct": 0.31,
        "buying_power": 170_847.00,
        "margin_used": 0.0,
        "currency": "USD",
        "as_of": "2025-01-15T20:00:00Z",
    }


@router.get("/positions")
async def get_positions(current_user: CurrentUser, db: DBSession):
    """Return open positions for the authenticated user."""
    # Demo positions for UI development
    return {
        "positions": [
            {
                "symbol": "AAPL",
                "asset_class": "equity",
                "side": "long",
                "quantity": 50,
                "avg_entry_price": 182.45,
                "current_price": 198.75,
                "market_value": 9_937.50,
                "unrealized_pnl": 815.00,
                "unrealized_pnl_pct": 8.94,
                "stop_loss": 175.00,
                "take_profit": 220.00,
            },
            {
                "symbol": "NVDA",
                "asset_class": "equity",
                "side": "long",
                "quantity": 20,
                "avg_entry_price": 475.00,
                "current_price": 498.50,
                "market_value": 9_970.00,
                "unrealized_pnl": 470.00,
                "unrealized_pnl_pct": 4.95,
                "stop_loss": 450.00,
                "take_profit": 550.00,
            },
            {
                "symbol": "BTC-USD",
                "asset_class": "crypto",
                "side": "long",
                "quantity": 0.15,
                "avg_entry_price": 42_000.00,
                "current_price": 47_250.00,
                "market_value": 7_087.50,
                "unrealized_pnl": 787.50,
                "unrealized_pnl_pct": 12.50,
                "stop_loss": 38_000.00,
                "take_profit": 55_000.00,
            },
        ]
    }


@router.get("/history")
async def get_trade_history(current_user: CurrentUser, db: DBSession):
    """Return closed trade history for the authenticated user."""
    return {
        "trades": [],
        "note": "Trade history persisted after live execution engine integration.",
    }


@router.get("/risk")
async def get_risk_metrics(current_user: CurrentUser, db: DBSession):
    """
    Return portfolio risk metrics: VaR, CVaR, Sharpe, Sortino, Beta, Alpha, Max Drawdown.
    Uses demo equity curve for UI development.
    """
    import random

    random.seed(42)
    # Synthetic daily returns for demo
    daily_returns = [random.gauss(0.001, 0.012) for _ in range(252)]
    equity_curve = [100_000.0]
    for r in daily_returns:
        equity_curve.append(equity_curve[-1] * (1 + r))

    # Synthetic benchmark returns (similar to SPY)
    benchmark_returns = [random.gauss(0.0009, 0.010) for _ in range(252)]

    var_95 = historical_var(daily_returns, 0.95)
    cvar_95 = cvar(daily_returns, 0.95)
    sharpe = sharpe_ratio(daily_returns)
    sortino = sortino_ratio(daily_returns)
    mdd, mdd_duration = max_drawdown(equity_curve)
    beta, alpha = beta_alpha(daily_returns, benchmark_returns)

    return {
        "var_95": round(var_95, 4),
        "cvar_95": round(cvar_95, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round((sum(daily_returns) / 252 * 252) / mdd if mdd > 0 else 0.0, 4),
        "max_drawdown": round(mdd, 4),
        "max_drawdown_duration_days": mdd_duration,
        "beta": beta,
        "alpha": round(alpha, 6),
        "note": "Risk metrics will use real portfolio returns after execution engine integration.",
    }
