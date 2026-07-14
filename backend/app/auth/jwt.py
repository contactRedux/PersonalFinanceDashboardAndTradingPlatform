"""
JWT creation and validation.

Access tokens: short-lived (15 min), HS256-signed.
Refresh tokens: longer-lived (7 days), stored in Redis for rotation/revocation.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import get_settings
from app.data.cache.redis_client import get_redis_pool

settings = get_settings()

REFRESH_TOKEN_PREFIX = "refresh_token:"  # nosec B105 — Redis key prefix, not a credential


def create_access_token(claims: dict) -> str:
    """Create a signed JWT access token with a 15-minute expiry."""
    payload = {
        **claims,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate an access token. Returns None on any failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def create_refresh_token(claims: dict) -> str:
    """
    Create a cryptographically random refresh token, store in Redis with TTL.
    Returns the opaque token string (not a JWT — stored server-side).
    """
    token = secrets.token_urlsafe(64)
    redis = await get_redis_pool()
    key = f"{REFRESH_TOKEN_PREFIX}{token}"
    payload = {**claims, "type": "refresh"}
    # Store as hash fields
    await redis.hset(key, mapping={k: str(v) for k, v in payload.items()})
    await redis.expire(key, settings.jwt_refresh_token_expire_days * 86400)
    return token


async def decode_refresh_token(token: str) -> dict | None:
    """
    Validate and consume a refresh token from Redis.
    The token is deleted on read (rotation — each refresh token is single-use).
    """
    redis = await get_redis_pool()
    key = f"{REFRESH_TOKEN_PREFIX}{token}"
    payload = await redis.hgetall(key)
    if not payload:
        return None
    # Consume (delete) the token — token family rotation
    await redis.delete(key)
    return payload


async def revoke_all_user_tokens(user_id: str) -> None:
    """Revoke all refresh tokens for a user (logout all sessions)."""
    redis = await get_redis_pool()
    # Scan for all refresh tokens belonging to this user
    async for key in redis.scan_iter(f"{REFRESH_TOKEN_PREFIX}*"):
        payload = await redis.hgetall(key)
        if payload.get("sub") == user_id:
            await redis.delete(key)
