"""API v1 router — aggregates all REST route modules."""

from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    auth,
    backtest,
    calendar,
    crypto,
    journal,
    macro,
    market,
    ml,
    news,
    options,
    orders,
    portfolio,
    screener,
    strategies,
    watchlist,
    workspaces,
)

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(market.router, prefix="/market", tags=["market"])
api_v1_router.include_router(news.router, prefix="/news", tags=["news"])
api_v1_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_v1_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_v1_router.include_router(screener.router, prefix="/screener", tags=["screener"])
api_v1_router.include_router(options.router, prefix="/options", tags=["options"])
api_v1_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_v1_router.include_router(macro.router, prefix="/macro", tags=["macro"])
api_v1_router.include_router(crypto.router, prefix="/crypto", tags=["crypto"])
api_v1_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_v1_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
api_v1_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_v1_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_v1_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_v1_router.include_router(journal.router, prefix="/journal", tags=["journal"])
api_v1_router.include_router(ml.router, prefix="/ml", tags=["ml"])
