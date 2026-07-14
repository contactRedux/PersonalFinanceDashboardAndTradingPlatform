"""Watchlist CRUD endpoints — full implementation in ST-7."""
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()


@router.get("")
async def list_watchlists(_: dict = CurrentUser):
    return {"watchlists": [], "note": "Watchlist CRUD in ST-7"}


@router.post("")
async def create_watchlist(_: dict = CurrentUser):
    return {"note": "Watchlist creation in ST-7"}


@router.put("/{watchlist_id}")
async def update_watchlist(watchlist_id: str, _: dict = CurrentUser):
    return {"note": f"Update {watchlist_id} in ST-7"}


@router.delete("/{watchlist_id}")
async def delete_watchlist(watchlist_id: str, _: dict = CurrentUser):
    return {"note": f"Delete {watchlist_id} in ST-7"}
