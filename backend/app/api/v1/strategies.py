"""
Saved strategy configurations — CRUD API.

Strategies are stored in the PostgreSQL `strategy_configs` table.

Endpoints:
  GET    /api/v1/strategies          — list saved strategies for current user
  POST   /api/v1/strategies          — save a new strategy config
  GET    /api/v1/strategies/{id}     — get a specific strategy
  DELETE /api/v1/strategies/{id}     — delete a saved strategy
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DBSession
from app.models.strategy_config import StrategyConfig

logger = structlog.get_logger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class SaveStrategyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    config: dict = Field(..., description="Node graph {nodes, edges}")


class StrategyResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    config: dict
    created_at: str
    updated_at: str


class StrategyListResponse(BaseModel):
    strategies: list[StrategyResponse]
    count: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _row_to_response(row: StrategyConfig) -> StrategyResponse:
    return StrategyResponse(
        id=str(row.id),
        user_id=str(row.user_id),
        name=row.name,
        description=row.description or "",
        config=row.config,
        created_at=row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
        updated_at=row.updated_at.isoformat() if row.updated_at else datetime.now(UTC).isoformat(),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=StrategyListResponse)
async def list_strategies(current_user: CurrentUser, db: DBSession):
    """List saved strategy configs for the current user."""
    user_id = uuid.UUID(current_user["sub"]) if _is_uuid(current_user["sub"]) else None
    if user_id is None:
        return StrategyListResponse(strategies=[], count=0)

    result = await db.execute(
        select(StrategyConfig)
        .where(StrategyConfig.user_id == user_id, StrategyConfig.is_active == True)  # noqa: E712
        .order_by(StrategyConfig.updated_at.desc())
    )
    rows = result.scalars().all()
    return StrategyListResponse(
        strategies=[_row_to_response(r) for r in rows],
        count=len(rows),
    )


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def save_strategy(body: SaveStrategyRequest, current_user: CurrentUser, db: DBSession):
    """Save a new strategy configuration."""
    if "nodes" not in body.config or "edges" not in body.config:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="config must contain 'nodes' and 'edges'",
        )

    user_id = uuid.UUID(current_user["sub"]) if _is_uuid(current_user["sub"]) else uuid.uuid4()
    row = StrategyConfig(
        user_id=user_id,
        name=body.name,
        description=body.description or None,
        config=body.config,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("strategies.saved", user_id=str(user_id), name=body.name)
    return _row_to_response(row)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, current_user: CurrentUser, db: DBSession):
    """Get a specific saved strategy by ID."""
    row = await _get_owned(strategy_id, current_user["sub"], db)
    return _row_to_response(row)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: str, current_user: CurrentUser, db: DBSession):
    """Delete a saved strategy (soft-delete via is_active=False)."""
    row = await _get_owned(strategy_id, current_user["sub"], db)
    row.is_active = False
    await db.commit()
    logger.info("strategies.deleted", user_id=current_user["sub"], strategy_id=strategy_id)
    return None


# ─── Private helpers ──────────────────────────────────────────────────────────


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


async def _get_owned(strategy_id: str, user_sub: str, db: AsyncSession) -> StrategyConfig:
    """Fetch a strategy row, enforcing ownership. Raises 404 if missing or not owned."""
    if not _is_uuid(strategy_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    sid = uuid.UUID(strategy_id)
    result = await db.execute(
        select(StrategyConfig).where(
            StrategyConfig.id == sid,
            StrategyConfig.is_active == True,  # noqa: E712
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    # Ownership check — compare as strings since JWT sub may not be a UUID in tests
    if str(row.user_id) != user_sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    return row
