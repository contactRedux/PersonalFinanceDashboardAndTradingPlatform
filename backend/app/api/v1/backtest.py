"""
Backtesting REST API router.

Endpoints:
  POST /api/v1/backtest/run      — run a backtest (vectorized or event-driven)
  POST /api/v1/backtest/wfo      — run walk-forward optimization
  POST /api/v1/backtest/optimize — Bayesian (Optuna) optimization
  POST /api/v1/backtest/report   — generate HTML report for a prior backtest
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter()

# ─── In-process result store for PDF generation ───────────────────────────────
# Keyed by run_id (UUID). TTL managed by Redis if available; fallback to dict.
_RESULT_CACHE: dict[str, Any] = {}

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
    run_id: str  # UUID for PDF report retrieval
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


class OptimizeRequest(BaseModel):
    symbol: str = Field("AAPL", description="Ticker symbol")
    timeframe: str = Field("1d", description="Bar timeframe")
    start: str = Field("2022-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")
    strategy: str = Field("sma_cross", description="Strategy name")
    param_space: dict = Field(
        default_factory=lambda: {"fast": [5, 50, 1], "slow": [20, 200, 5]},
        description="Mapping of param_name → [low, high, step]",
    )
    n_trials: int = Field(30, ge=3, le=300, description="Number of Optuna trials")
    metric: str = Field("sharpe_ratio", description="Metric to maximise")
    initial_capital: float = Field(100_000.0, gt=0)


class TrialSchema(BaseModel):
    number: int
    params: dict
    value: float | None
    state: str


class OptimizeResponse(BaseModel):
    best_params: dict
    best_value: float
    n_trials: int
    metric: str
    trials: list[TrialSchema]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_strategy(name: str, params: dict):
    """Return an instantiated strategy by name."""
    from backtesting.strategies.bollinger_band import BollingerBandStrategy  # noqa: PLC0415
    from backtesting.strategies.macd_cross import MACDCrossStrategy  # noqa: PLC0415
    from backtesting.strategies.rsi_mean_reversion import RSIMeanReversionStrategy  # noqa: PLC0415
    from backtesting.strategies.sma_cross import SmaCrossStrategy  # noqa: PLC0415
    from backtesting.strategies.vwap_reversion import VWAPReversionStrategy  # noqa: PLC0415

    strategies = {
        "sma_cross": SmaCrossStrategy,
        "rsi_mean_reversion": RSIMeanReversionStrategy,
        "macd_cross": MACDCrossStrategy,
        "bollinger_band": BollingerBandStrategy,
        "vwap_reversion": VWAPReversionStrategy,
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
    from backtesting.strategies.bollinger_band import BollingerBandStrategy  # noqa: PLC0415
    from backtesting.strategies.macd_cross import MACDCrossStrategy  # noqa: PLC0415
    from backtesting.strategies.rsi_mean_reversion import RSIMeanReversionStrategy  # noqa: PLC0415
    from backtesting.strategies.sma_cross import SmaCrossStrategy  # noqa: PLC0415
    from backtesting.strategies.vwap_reversion import VWAPReversionStrategy  # noqa: PLC0415

    strategies = {
        "sma_cross": SmaCrossStrategy,
        "rsi_mean_reversion": RSIMeanReversionStrategy,
        "macd_cross": MACDCrossStrategy,
        "bollinger_band": BollingerBandStrategy,
        "vwap_reversion": VWAPReversionStrategy,
    }
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

    # Store result for PDF generation (in-process; TTL via LRU if needed)
    run_id = str(uuid.uuid4())
    _RESULT_CACHE[run_id] = result
    # Cap cache size at 100 entries
    if len(_RESULT_CACHE) > 100:
        oldest = next(iter(_RESULT_CACHE))
        _RESULT_CACHE.pop(oldest, None)

    return BacktestRunResponse(
        run_id=run_id,
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


@router.post("/optimize", response_model=OptimizeResponse)
async def run_bayesian_optimize(body: OptimizeRequest, current_user: CurrentUser):
    """
    Run Bayesian (Optuna TPE) optimization for a strategy.

    Returns best params, best metric value, and all trial results.
    """
    try:
        from backtesting.engine.vectorized import VectorizedEngine  # noqa: PLC0415
        from backtesting.optimization.bayesian import BayesianOptimizer  # noqa: PLC0415
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Backtesting engine not available: {e}",
        ) from e

    strategy_cls = _get_strategy_cls(body.strategy)
    data = _fetch_data(body.symbol, body.timeframe, body.start, body.end)

    # Convert param_space list [low, high, step] → tuple
    param_space: dict = {}
    for name, spec in body.param_space.items():
        if not isinstance(spec, (list, tuple)) or len(spec) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"param_space['{name}'] must be [low, high, step]",
            )
        param_space[name] = (float(spec[0]), float(spec[1]), float(spec[2]))

    optimizer = BayesianOptimizer(
        strategy_class=strategy_cls,
        param_space=param_space,
        engine_cls=VectorizedEngine,
        metric=body.metric,
        n_trials=body.n_trials,
        engine_kwargs={"initial_capital": body.initial_capital},
    )

    try:
        result = optimizer.run(data, symbol=body.symbol, timeframe=body.timeframe)
    except Exception as e:  # noqa: BLE001
        logger.error("backtest.optimize.error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bayesian optimization failed.",
        ) from e

    return OptimizeResponse(
        best_params=result.best_params,
        best_value=result.best_value,
        n_trials=result.n_trials,
        metric=result.metric,
        trials=[
            TrialSchema(
                number=t["number"],
                params=t["params"],
                value=t["value"],
                state=t["state"],
            )
            for t in result.trials
        ],
    )


# ─── Grid Search Optimizer ────────────────────────────────────────────────────


class GridSearchRequest(BaseModel):
    symbol: str = Field("AAPL", description="Ticker symbol")
    timeframe: str = Field("1d", description="Bar timeframe")
    start: str = Field("2022-01-01", description="ISO date YYYY-MM-DD")
    end: str = Field("2024-01-01", description="ISO date YYYY-MM-DD")
    strategy: str = Field("sma_cross", description="Strategy name")
    param_space: dict = Field(
        default_factory=lambda: {"fast": [10, 20, 30], "slow": [40, 50, 60]},
        description="Mapping of param_name → list of values",
    )
    metric: str = Field("sharpe_ratio", description="Metric to maximise")
    initial_capital: float = Field(100_000.0, gt=0)


class GridSearchResponse(BaseModel):
    best_params: dict
    best_value: float
    metric: str
    n_combinations: int
    top_results: list[dict]


@router.post("/grid-search", response_model=GridSearchResponse)
async def run_grid_search(body: GridSearchRequest, current_user: CurrentUser):
    """
    Run exhaustive grid search optimization for a strategy.

    Returns best params, best metric value, and all evaluated combinations ranked.
    """
    try:
        from backtesting.engine.vectorized import VectorizedEngine  # noqa: PLC0415
        from backtesting.optimization.grid_search import GridSearchOptimizer  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Grid search optimizer not available: {exc}",
        ) from exc

    strategy_cls = _get_strategy_cls(body.strategy)
    data = _fetch_data(body.symbol, body.timeframe, body.start, body.end)

    # param_space for grid search is list of values per param
    for name, values in body.param_space.items():
        if not isinstance(values, list) or len(values) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"param_space['{name}'] must be a non-empty list of values",
            )

    optimizer = GridSearchOptimizer(
        strategy_class=strategy_cls,
        param_space=body.param_space,
        engine_cls=VectorizedEngine,
        metric=body.metric,
        engine_kwargs={"initial_capital": body.initial_capital},
    )

    try:
        result = optimizer.run(data, symbol=body.symbol, timeframe=body.timeframe)
    except Exception as exc:  # noqa: BLE001
        logger.error("backtest.grid_search.error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Grid search optimization failed.",
        ) from exc

    return GridSearchResponse(
        best_params=result.best_params,
        best_value=result.best_value,
        metric=result.metric,
        n_combinations=result.n_combinations,
        top_results=result.all_results[:20],
    )


# ─── PDF Report ───────────────────────────────────────────────────────────────


@router.get("/{run_id}/report/pdf")
async def get_pdf_report(run_id: str, current_user: CurrentUser):
    """
    Stream the PDF performance report for a completed backtest run.

    run_id must match a run_id returned by POST /backtest/run.
    Report is generated on-demand via WeasyPrint from the HTML report template.
    """
    result = _RESULT_CACHE.get(run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backtest result not found. run_id may have expired or be invalid.",
        )

    try:
        import sys  # noqa: PLC0415, F811

        # Ensure backtesting package is on path
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        from backtesting.reporting.pdf_report import generate_pdf_report  # noqa: PLC0415

        pdf_bytes = generate_pdf_report(result)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"PDF generation not available: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("backtest.pdf_report.error", run_id=run_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation failed.",
        ) from exc

    filename = f"backtest_{result.symbol}_{run_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
