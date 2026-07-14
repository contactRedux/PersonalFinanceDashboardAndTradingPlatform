"""
FastAPI dependency injection providers.
All shared resources (DB session, Redis, auth) are requested via Depends().
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.data.cache.redis_client import get_redis_pool
from app.database import AsyncSessionLocal

_bearer = HTTPBearer(auto_error=True)


# ─── Database session ─────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DBSession = Annotated[AsyncSession, Depends(get_db)]


# ─── Redis ────────────────────────────────────────────────────────────────────
async def get_redis():
    return await get_redis_pool()


RedisClient = Annotated[object, Depends(get_redis)]


# ─── Auth: current user from JWT Bearer ───────────────────────────────────────
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    """Decode and validate the Bearer JWT; return the claims payload."""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


CurrentUser = Annotated[dict, Depends(get_current_user)]


# ─── RBAC: role enforcement ────────────────────────────────────────────────────
def require_role(*roles: str):
    """Dependency factory — raises 403 if the current user's role is not in roles."""

    async def _check(current_user: CurrentUser) -> dict:
        if current_user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return _check
