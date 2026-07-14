"""Crypto-specific endpoints — full implementation in ST-10."""
from fastapi import APIRouter, Query

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("/funding-rates")
async def get_funding_rates(
    _: CurrentUser,
    symbols: str = Query(None),
):
    return {"rates": [], "note": "Crypto funding rates in ST-10"}


@router.get("/onchain/{symbol}")
async def get_onchain_metrics(symbol: str, _: CurrentUser):
    return {"symbol": symbol.upper(), "metrics": {}, "note": "On-chain metrics in ST-10"}


@router.get("/liquidations")
async def get_liquidation_levels(_: CurrentUser):
    return {"levels": [], "note": "Liquidation heatmap in ST-10"}


@router.get("/exchange-flows")
async def get_exchange_flows(_: CurrentUser):
    return {"flows": [], "note": "Exchange flows in ST-10"}
