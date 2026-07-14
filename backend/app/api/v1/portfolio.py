"""Portfolio REST endpoints — implemented in ST-9."""
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("")
async def get_portfolio(_: dict = CurrentUser):
    return {
        "equity": 0, "cash": 0, "unrealized_pnl": 0,
        "realized_pnl": 0, "note": "Portfolio in ST-9",
    }


@router.get("/positions")
async def get_positions(_: dict = CurrentUser):
    return {"positions": [], "note": "Positions in ST-9"}


@router.get("/history")
async def get_trade_history(_: dict = CurrentUser):
    return {"trades": [], "note": "Trade history in ST-9"}


@router.get("/risk")
async def get_risk_metrics(_: dict = CurrentUser):
    return {"var": None, "cvar": None, "sharpe": None, "note": "Risk metrics in ST-9"}
