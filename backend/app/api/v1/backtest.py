"""
Backtesting REST API router.

Endpoints:
  POST /api/v1/backtest/run     — run a backtest (vectorized or event-driven)
  POST /api/v1/backtest/wfo     — run walk-forward optimization
  POST /api/v1/backtest/report  — generate HTML report for a prior backtest
"""

from __future__ import annotations

import os
import sys

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter()

# ─── Add backtesting package to path (monorepo root) ─────────────────────────
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ─── Request / Response schemas ───────────────────────────────────────────────


class BacktestRunRequest(BaseModel):
    symbol: str = Field("AAPL", description="Ticker symbol")
    timeframe: str = Field("1d", description="Bar timeframe: 1d, 1h, etc.")
    start: str = Field("2022-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")
    strategy: str = Field("sma_cross", description="Strategy name")
    params: dict = Field(default_factory=dict, description="Strategy parameters")
    engine: str = Field("vectorized", description="vectorized | event_driven")
    initial_capital: float = Field(100_000.0, gt=0)
    commission: float = Field(0.001, ge=0, le=0.05)
    run_monte_carlo: bool = Field(False, description="Also run Monte Carlo simulation")
    mc_simulations: int = Field(500, ge=100, le=10_000)


class TradeSchema(BaseModel):
    entry_time: str
    exit_time: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float


class BacktestRunResponse(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_curve: list[float]
    trades: list[TradeSchema]
    monte_carlo: dict | None = None


class WfoRequest(BaseModel):
    symbol: str = "AAPL"
    timeframe: str = "1d"
    start: str = "2019-01-01"
    end: str = "2024-01-01"
    strategy: str = "sma_cross"
    param_grid: dict = Field(default_factory=lambda: {"fast": [10, 20], "slow": [40, 50, 60]})
    in_sample_bars: int = Field(252, gt=50)
    out_of_sample_bars: int = Field(63, gt=10)
    metric: str = "sharpe_ratio"
    initial_capital: float = 100_000.0


class WfoFoldSchema(BaseModel):
    fold: int
    in_sample_start: str
    in_sample_end: str
    out_of_sample_start: str
    out_of_sample_end: str
    best_params: dict
    in_sample_metric: float
    oos_total_return_pct: float
    oos_sharpe: float
    oos_trades: int


class WfoResponse(BaseModel):
    folds: list[WfoFoldSchema]
    avg_oos_sharpe: float
    avg_oos_return_pct: float
    total_oos_trades: int
    combined_equity: list[float]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_strategy(name: str, params: dict):
    """Return an instantiated strategy by name."""
    from backtesting.strategies.sma_cross import SmaCrossStrategy  # noqa: PLC0415

    strategies = {
        "sma_cross": SmaCrossStrategy,
    }
    cls = strategies.get(name.lower())
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown strategy '{name}'. Available: {list(strategies)}",
        )
    try:
        return cls(**params)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy params: {e}",
        ) from e


def _get_strategy_cls(name: str):
    from backtesting.strategies.sma_cross import SmaCrossStrategy  # noqa: PLC0415

    strategies = {"sma_cross": SmaCrossStrategy}
    cls = strategies.get(name.lower())
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown strategy '{name}'.",
        )
    return cls


def _fetch_data(symbol: str, timeframe: str, start: str, end: str):
    """Fetch OHLCV data from the market data provider."""
    import pandas as pd  # noqa: PLC0415

    from app.services.market_data.router import get_provider  # noqa: PLC0415

    provider = get_provider()
    # get_bars is sync in yfinance provider — run via asyncio if needed
    import asyncio  # noqa: PLC0415

    try:
        loop = asyncio.get_event_loop()
        bars = loop.run_until_complete(
            provider.get_bars(symbol, timeframe, start=start, end=end, limit=5000)
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch market data: {e}",
        ) from e

    if not bars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data returned for {symbol} {timeframe} {start}→{end}",
        )

    df = pd.DataFrame(bars)
    # Normalise column names
    df.columns = [c.lower() for c in df.columns]
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Market data missing column: {col}",
            )
    if "timestamp" in df.columns:
        df.index = pd.to_datetime(df["timestamp"])
    elif "time" in df.columns:
        df.index = pd.to_datetime(df["time"])
    return df


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(body: BacktestRunRequest, current_user: CurrentUser):
    """
    Run a backtest over historical data.

    Returns equity curve, trade log, and all performance metrics.
    Optionally runs Monte Carlo simulation on the trade P&L.
    """
    try:
        from backtesting.engine.event_driven import EventDrivenEngine  # noqa: PLC0415
        from backtesting.engine.vectorized import VectorizedEngine  # noqa: PLC0415
        from backtesting.optimization.monte_carlo import MonteCarlo  # noqa: PLC0415
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Backtesting engine not available: {e}",
        ) from e

    strategy = _get_strategy(body.strategy, body.params)
    data = _fetch_data(body.symbol, body.timeframe, body.start, body.end)

    engine_cls = VectorizedEngine if body.engine == "vectorized" else EventDrivenEngine
    engine = engine_cls(initial_capital=body.initial_capital, commission=body.commission)

    try:
        result = engine.run(data, strategy, symbol=body.symbol, timeframe=body.timeframe)
        result.compute_metrics()
    except Exception as e:  # noqa: BLE001
        logger.error("backtest.run.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backtest execution failed.",
        ) from e

    mc_dict = None
    if body.run_monte_carlo and result.trades:
        mc = MonteCarlo(n_simulations=body.mc_simulations, seed=42)
        mc_result = mc.run(result)
        mc_dict = {
            "n_simulations": mc_result.n_simulations,
            "p05_final_equity": mc_result.p05_final_equity,
            "median_final_equity": mc_result.median_final_equity,
            "p95_final_equity": mc_result.p95_final_equity,
            "p05_max_drawdown": mc_result.p05_max_drawdown,
            "median_max_drawdown": mc_result.median_max_drawdown,
            "prob_profit": mc_result.prob_profit,
        }

    trades = [
        TradeSchema(
            entry_time=str(t.entry_time),
            exit_time=str(t.exit_time),
            symbol=t.symbol,
            direction=t.direction,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            quantity=t.quantity,
            pnl=t.pnl,
            pnl_pct=t.pnl_pct,
        )
        for t in result.trades
    ]

    return BacktestRunResponse(
        symbol=result.symbol,
        timeframe=result.timeframe,
        start=str(result.start.date()),
        end=str(result.end.date()),
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        total_return_pct=result.total_return_pct,
        cagr_pct=result.cagr * 100.0,
        sharpe_ratio=result.sharpe_ratio,
        sortino_ratio=result.sortino_ratio,
        calmar_ratio=result.calmar_ratio,
        max_drawdown_pct=result.max_drawdown_pct,
        win_rate=result.win_rate * 100.0,
        profit_factor=result.profit_factor if result.profit_factor != float("inf") else 999.0,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        equity_curve=result.equity_curve,
        trades=trades,
        monte_carlo=mc_dict,
    )


@router.post("/wfo", response_model=WfoResponse)
async def run_walk_forward(body: WfoRequest, current_user: CurrentUser):
    """
    Run a walk-forward optimization.

    Returns per-fold results and combined OOS equity curve.
    """
    try:
        from backtesting.engine.vectorized import VectorizedEngine  # noqa: PLC0415
        from backtesting.optimization.walk_forward import WalkForwardOptimizer  # noqa: PLC0415
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Backtesting engine not available: {e}",
        ) from e

    strategy_cls = _get_strategy_cls(body.strategy)
    data = _fetch_data(body.symbol, body.timeframe, body.start, body.end)

    optimizer = WalkForwardOptimizer(
        engine_cls=VectorizedEngine,
        param_grid=body.param_grid,
        in_sample_bars=body.in_sample_bars,
        out_of_sample_bars=body.out_of_sample_bars,
        metric=body.metric,
        engine_kwargs={"initial_capital": body.initial_capital},
    )

    try:
        wf = optimizer.run(data, strategy_cls, symbol=body.symbol, timeframe=body.timeframe)
    except Exception as e:  # noqa: BLE001
        logger.error("backtest.wfo.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Walk-forward optimization failed.",
        ) from e

    folds = []
    for f in wf.folds:
        oos = f.out_of_sample_result
        oos.compute_metrics()
        folds.append(
            WfoFoldSchema(
                fold=f.fold,
                in_sample_start=str(f.in_sample_start.date()),
                in_sample_end=str(f.in_sample_end.date()),
                out_of_sample_start=str(f.out_of_sample_start.date()),
                out_of_sample_end=str(f.out_of_sample_end.date()),
                best_params=f.best_params,
                in_sample_metric=f.in_sample_metric,
                oos_total_return_pct=oos.total_return_pct,
                oos_sharpe=oos.sharpe_ratio,
                oos_trades=oos.total_trades,
            )
        )

    return WfoResponse(
        folds=folds,
        avg_oos_sharpe=wf.avg_oos_sharpe,
        avg_oos_return_pct=wf.avg_oos_return,
        total_oos_trades=wf.total_oos_trades,
        combined_equity=wf.combined_equity,
    )
