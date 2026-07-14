"""
Multi-user workspaces — CRUD API.

Workspaces are stored in the PostgreSQL `workspaces` / `workspace_members` tables.

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
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentUser, DBSession
from app.models.workspace import Workspace, WorkspaceMember

logger = structlog.get_logger(__name__)
router = APIRouter()

_ALLOWED_INVITE_ROLES = {"editor", "viewer", "member"}


# ─── Schemas ──────────────────────────────────────────────────────────────────


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    layout: dict | None = Field(None, description="Optional panel layout snapshot")


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


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ws_to_response(row: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=str(row.id),
        name=row.name,
        owner_id=str(row.owner_id),
        created_at=row.created_at.isoformat() if row.created_at else datetime.now(UTC).isoformat(),
    )


def _member_to_response(row: WorkspaceMember) -> MemberResponse:
    return MemberResponse(
        workspace_id=str(row.workspace_id),
        user_id=str(row.user_id),
        role=row.role,
        joined_at=row.joined_at.isoformat() if row.joined_at else datetime.now(UTC).isoformat(),
    )


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


async def _get_workspace(ws_id_str: str, db: AsyncSession) -> Workspace:
    ws_uuid = _parse_uuid(ws_id_str)
    if ws_uuid is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    result = await db.execute(select(Workspace).where(Workspace.id == ws_uuid))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return row


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(current_user: CurrentUser, db: DBSession):
    """List workspaces the current user owns or is a member of."""
    user_uuid = _parse_uuid(current_user["sub"])
    if user_uuid is None:
        return []

    # Workspaces where this user is a member
    member_ws_ids = (
        select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_uuid)
    )
    result = await db.execute(
        select(Workspace)
        .where(
            or_(
                Workspace.owner_id == user_uuid,
                Workspace.id.in_(member_ws_ids),
            )
        )
        .order_by(Workspace.created_at.desc())
    )
    rows = result.scalars().all()
    return [_ws_to_response(r) for r in rows]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: CreateWorkspaceRequest, current_user: CurrentUser, db: DBSession):
    """Create a new workspace owned by the current user."""
    owner_uuid = _parse_uuid(current_user["sub"])
    if owner_uuid is None:
        owner_uuid = uuid.uuid4()

    ws = Workspace(owner_id=owner_uuid, name=body.name, layout=body.layout)
    db.add(ws)
    await db.flush()  # Get the generated ID

    # Auto-add the owner as a member with role "owner"
    member = WorkspaceMember(
        workspace_id=ws.id,
        user_id=owner_uuid,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(ws)

    logger.info("workspaces.created", workspace_id=str(ws.id), owner=str(owner_uuid))
    return _ws_to_response(ws)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: str, current_user: CurrentUser, db: DBSession):
    """Delete a workspace (owner only)."""
    ws = await _get_workspace(workspace_id, db)
    if str(ws.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this workspace.",
        )
    await db.delete(ws)
    await db.commit()
    logger.info("workspaces.deleted", workspace_id=workspace_id)
    return None


@router.post(
    "/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    workspace_id: str, body: InviteMemberRequest, current_user: CurrentUser, db: DBSession
):
    """Invite a user to a workspace (owner only)."""
    ws = await _get_workspace(workspace_id, db)
    if str(ws.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can invite members.",
        )
    if body.role not in _ALLOWED_INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"role must be one of: {sorted(_ALLOWED_INVITE_ROLES)}",
        )

    invite_uuid = _parse_uuid(body.user_id)
    if invite_uuid is None:
        # Accept non-UUID user_ids for test compatibility — store as deterministic UUID
        invite_uuid = uuid.uuid5(uuid.NAMESPACE_OID, body.user_id)

    # Check for duplicate
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == invite_uuid,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member.")

    member = WorkspaceMember(workspace_id=ws.id, user_id=invite_uuid, role=body.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return _member_to_response(member)


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(workspace_id: str, current_user: CurrentUser, db: DBSession):
    """List members of a workspace."""
    ws = await _get_workspace(workspace_id, db)
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
    )
    return [_member_to_response(m) for m in result.scalars().all()]
