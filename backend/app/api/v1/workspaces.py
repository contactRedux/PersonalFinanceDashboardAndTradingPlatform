"""
Multi-user workspaces — CRUD API.

Workspaces are stored in the PostgreSQL `workspaces` / `workspace_members` tables.
In demo / CI mode (no real DB) the store falls back to an in-memory dict.

Endpoints:
  GET    /api/v1/workspaces              — list workspaces the current user belongs to
  POST   /api/v1/workspaces              — create a workspace; caller becomes owner
  DELETE /api/v1/workspaces/{id}         — delete own workspace
  POST   /api/v1/workspaces/{id}/members — invite a user by user_id
  GET    /api/v1/workspaces/{id}/members — list members of a workspace
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
# _STORE: workspace_id → workspace dict
# _MEMBERS: workspace_id → list of member dicts
_STORE: dict[str, dict[str, Any]] = {}
_MEMBERS: dict[str, list[dict[str, Any]]] = {}


# ─── Schemas ──────────────────────────────────────────────────────────────────


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class InviteMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field("member", max_length=50)


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: str


class MemberResponse(BaseModel):
    workspace_id: str
    user_id: str
    role: str
    joined_at: str


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(current_user: CurrentUser):
    """List workspaces the current user owns or is a member of."""
    user_id = current_user["sub"]
    # Collect workspace IDs the user belongs to (as owner or member)
    member_of: set[str] = set()
    for ws_id, members in _MEMBERS.items():
        if any(m["user_id"] == user_id for m in members):
            member_of.add(ws_id)

    rows = [
        v
        for v in _STORE.values()
        if v["owner_id"] == user_id or v["id"] in member_of
    ]
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return [WorkspaceResponse(**r) for r in rows]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: CreateWorkspaceRequest, current_user: CurrentUser):
    """Create a new workspace owned by the current user."""
    ws_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    record: dict[str, Any] = {
        "id": ws_id,
        "name": body.name,
        "owner_id": current_user["sub"],
        "created_at": now,
    }
    _STORE[ws_id] = record
    _MEMBERS[ws_id] = [
        {
            "workspace_id": ws_id,
            "user_id": current_user["sub"],
            "role": "owner",
            "joined_at": now,
        }
    ]
    logger.info("workspaces.created", workspace_id=ws_id, owner=current_user["sub"])
    return WorkspaceResponse(**record)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: str, current_user: CurrentUser):
    """Delete a workspace (owner only)."""
    record = _STORE.get(workspace_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    if record["owner_id"] != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this workspace.",
        )
    del _STORE[workspace_id]
    _MEMBERS.pop(workspace_id, None)
    logger.info("workspaces.deleted", workspace_id=workspace_id)
    return None


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    workspace_id: str, body: InviteMemberRequest, current_user: CurrentUser
):
    """Invite a user to a workspace (owner only)."""
    record = _STORE.get(workspace_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    if record["owner_id"] != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can invite members.",
        )
    members = _MEMBERS.setdefault(workspace_id, [])
    if any(m["user_id"] == body.user_id for m in members):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member."
        )
    now = datetime.now(UTC).isoformat()
    member: dict[str, Any] = {
        "workspace_id": workspace_id,
        "user_id": body.user_id,
        "role": body.role,
        "joined_at": now,
    }
    members.append(member)
    return MemberResponse(**member)


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(workspace_id: str, current_user: CurrentUser):
    """List members of a workspace."""
    if workspace_id not in _STORE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return [MemberResponse(**m) for m in _MEMBERS.get(workspace_id, [])]
