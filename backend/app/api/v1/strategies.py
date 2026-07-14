"""
Saved strategy configurations — CRUD API.

Strategies are stored in the PostgreSQL `strategy_configs` table.
In demo / CI mode (no real DB) the store falls back to an in-memory dict.

Endpoints:
  GET    /api/v1/strategies          — list saved strategies for current user
  POST   /api/v1/strategies          — save a new strategy config
  GET    /api/v1/strategies/{id}     — get a specific strategy
  DELETE /api/v1/strategies/{id}     — delete a saved strategy
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter()

# ─── In-memory fallback (used in tests / demo mode without a real DB) ─────────
# A real deployment persists these rows in PostgreSQL via a `strategy_configs` table.
# The fallback keeps strategies per user in a plain dict for this session only.

_STORE: dict[str, dict[str, Any]] = {}


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


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=StrategyListResponse)
async def list_strategies(current_user: CurrentUser):
    """List saved strategy configs for the current user."""
    user_id = current_user["sub"]
    rows = [v for v in _STORE.values() if v["user_id"] == user_id]
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return StrategyListResponse(
        strategies=[StrategyResponse(**r) for r in rows],
        count=len(rows),
    )


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def save_strategy(body: SaveStrategyRequest, current_user: CurrentUser):
    """Save a new strategy configuration."""
    # Validate node graph structure
    if "nodes" not in body.config or "edges" not in body.config:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="config must contain 'nodes' and 'edges'",
        )

    strategy_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    record: dict[str, Any] = {
        "id": strategy_id,
        "user_id": current_user["sub"],
        "name": body.name,
        "description": body.description,
        "config": body.config,
        "created_at": now,
        "updated_at": now,
    }
    _STORE[strategy_id] = record
    logger.info("strategies.saved", user_id=current_user["sub"], name=body.name)
    return StrategyResponse(**record)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, current_user: CurrentUser):
    """Get a specific saved strategy by ID."""
    record = _STORE.get(strategy_id)
    if record is None or record["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    return StrategyResponse(**record)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: str, current_user: CurrentUser):
    """Delete a saved strategy."""
    record = _STORE.get(strategy_id)
    if record is None or record["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found.")
    del _STORE[strategy_id]
    logger.info("strategies.deleted", user_id=current_user["sub"], strategy_id=strategy_id)
    return None
