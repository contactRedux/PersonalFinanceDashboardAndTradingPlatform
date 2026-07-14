"""
Watchlist CRUD endpoints.
Stores per-user watchlists in PostgreSQL. Persists the symbol list
so it's available server-side for alert evaluation and screener defaults.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update

from app.dependencies import CurrentUser, DBSession
from app.models.watchlist import Watchlist

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────
class WatchlistResponse(BaseModel):
    id: str
    name: str
    symbols: list[str]
    is_default: bool


class CreateWatchlistRequest(BaseModel):
    name: str
    symbols: list[str] = []


class UpdateWatchlistRequest(BaseModel):
    name: str | None = None
    symbols: list[str] | None = None
    is_default: bool | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────
@router.get("", response_model=list[WatchlistResponse])
async def list_watchlists(current_user: CurrentUser, db: DBSession):
    """Return all watchlists for the authenticated user."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == current_user["sub"])
        .order_by(Watchlist.is_default.desc(), Watchlist.created_at)
    )
    watchlists = result.scalars().all()
    return [
        WatchlistResponse(
            id=str(w.id),
            name=w.name,
            symbols=w.symbols or [],
            is_default=w.is_default,
        )
        for w in watchlists
    ]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: CreateWatchlistRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a new watchlist for the authenticated user."""
    watchlist = Watchlist(
        user_id=uuid.UUID(current_user["sub"]),
        name=body.name,
        symbols=body.symbols,
        is_default=False,
    )
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)
    return WatchlistResponse(
        id=str(watchlist.id),
        name=watchlist.name,
        symbols=watchlist.symbols or [],
        is_default=watchlist.is_default,
    )


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: str,
    body: UpdateWatchlistRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Update a watchlist's name, symbols, or default status."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == uuid.UUID(watchlist_id),
            Watchlist.user_id == current_user["sub"],
        )
    )
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found.")

    updates = body.model_dump(exclude_none=True)
    if updates:
        await db.execute(
            update(Watchlist)
            .where(Watchlist.id == uuid.UUID(watchlist_id))
            .values(**updates)
        )
        await db.commit()
        await db.refresh(watchlist)

    return WatchlistResponse(
        id=str(watchlist.id),
        name=watchlist.name,
        symbols=watchlist.symbols or [],
        is_default=watchlist.is_default,
    )


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Delete a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == uuid.UUID(watchlist_id),
            Watchlist.user_id == current_user["sub"],
        )
    )
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found.")
    await db.delete(watchlist)
    await db.commit()
    return None
