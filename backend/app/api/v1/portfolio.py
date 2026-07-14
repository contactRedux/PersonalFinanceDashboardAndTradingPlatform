"""
Portfolio REST endpoints.

For now, serves paper-trading portfolio data from PostgreSQL.
Live brokerage integration is deferred to the C++ execution engine phase.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models.order import Order
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


@router.get("/trades")
async def get_trades(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Return filled trade history for the authenticated user.

    Queries the orders table for filled orders, ordered most-recent first.
    Returns an empty list when no filled orders exist.
    """
    stmt = (
        select(Order)
        .where(
            Order.user_id == current_user["sub"],
            Order.status == "filled",
        )
        .order_by(Order.filled_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = list(result.scalars().all())

    trades = [
        {
            "id": str(o.broker_order_id or o.id),
            "symbol": o.symbol,
            "side": o.side,
            "quantity": o.quantity,
            "entry_price": o.filled_avg_price,
            "exit_price": None,
            "entry_time": o.submitted_at.isoformat() if o.submitted_at else None,
            "exit_time": o.filled_at.isoformat() if o.filled_at else None,
            "pnl": None,
            "pnl_pct": None,
        }
        for o in orders
    ]
    return {"trades": trades, "count": len(trades)}


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


# ─── In-memory position store (demo / CI mode without a real DB) ─────────────
_IMPORTED_POSITIONS: dict[str, list[dict[str, Any]]] = {}

_MAX_UPLOAD_BYTES = 1_048_576  # 1 MB
_MAX_ROWS = 1_000


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_portfolio_csv(
    file: UploadFile,
    current_user: CurrentUser,
):
    """
    Accept a multipart CSV upload (field: ``file``) and upsert positions.

    Required columns: symbol, quantity, avg_price
    Optional column:  date_opened

    Returns ``{"imported": N, "positions": [...]}`` on success.
    Returns 422 with row-level details on validation errors.
    """
    raw = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File exceeds 1 MB limit.",
        )

    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    required = {"symbol", "quantity", "avg_price"}
    if reader.fieldnames is None or not required.issubset(
        {f.strip().lower() for f in reader.fieldnames if f}
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV must contain columns: {', '.join(sorted(required))}",
        )

    positions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for row_idx, row in enumerate(reader, start=2):  # row 1 = header
        if len(positions) >= _MAX_ROWS:
            errors.append({"row": row_idx, "error": f"Exceeds {_MAX_ROWS}-row limit"})
            break

        # Normalise keys to lowercase-stripped
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}

        symbol = row.get("symbol", "").upper()
        qty_raw = row.get("quantity", "")
        price_raw = row.get("avg_price", "")

        row_errors: list[str] = []
        if not symbol:
            row_errors.append("symbol is empty")

        try:
            qty = float(qty_raw)
            if qty <= 0:
                row_errors.append(f"quantity must be > 0, got {qty_raw!r}")
        except ValueError:
            qty = 0.0
            row_errors.append(f"quantity is not a number: {qty_raw!r}")

        try:
            avg_price = float(price_raw)
            if avg_price <= 0:
                row_errors.append(f"avg_price must be > 0, got {price_raw!r}")
        except ValueError:
            avg_price = 0.0
            row_errors.append(f"avg_price is not a number: {price_raw!r}")

        if row_errors:
            errors.append({"row": row_idx, "errors": row_errors})
            continue

        position: dict[str, Any] = {
            "symbol": symbol,
            "quantity": qty,
            "avg_price": avg_price,
        }
        if row.get("date_opened"):
            position["date_opened"] = row["date_opened"]
        positions.append(position)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation errors in CSV", "rows": errors},
        )

    # Upsert into in-memory store keyed by user_id → symbol
    # Duplicate symbols → weighted-average price, additive quantity
    user_id = current_user["sub"]
    store = _IMPORTED_POSITIONS.setdefault(user_id, [])
    existing = {p["symbol"]: i for i, p in enumerate(store)}
    for pos in positions:
        sym = pos["symbol"]
        if sym in existing:
            old = store[existing[sym]]
            old_qty = old["quantity"]
            old_avg = old["avg_price"]
            new_qty = pos["quantity"]
            new_avg = pos["avg_price"]
            combined_qty = old_qty + new_qty
            combined_avg = (old_avg * old_qty + new_avg * new_qty) / combined_qty
            merged: dict[str, Any] = {**old, "quantity": combined_qty, "avg_price": combined_avg}
            if pos.get("date_opened"):
                merged["date_opened"] = pos["date_opened"]
            store[existing[sym]] = merged
        else:
            store.append(pos)

    return {"imported": len(positions), "positions": positions}


@router.post("/import/broker", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def import_broker(
    current_user: CurrentUser,
):
    """Broker OAuth import — not yet implemented in production."""
    return {
        "status": "not_implemented",
        "message": (
            "Broker OAuth integration requires production credentials. Contact support."
        ),
        "supported_brokers": ["alpaca", "td_ameritrade", "interactive_brokers"],
    }
