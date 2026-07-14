"""
services/audit/logger.py — Async audit log writer.

Records security-sensitive actions (auth events, trade mutations, config changes)
to the `audit_log` PostgreSQL table. All writes are fire-and-forget to avoid
blocking request handlers. Failures are logged but never re-raised.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def write_audit_log(
    db: AsyncSession,
    *,
    user_id: str | uuid.UUID | None,
    action: str,
    resource: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Write an audit log entry asynchronously.

    Args:
        db:         SQLAlchemy async session (caller owns the transaction).
        user_id:    UUID of the acting user (None for pre-auth events).
        action:     Short verb describing the action, e.g. "auth.login".
        resource:   Resource identifier, e.g. "/api/v1/auth/login".
        details:    Optional free-form JSONB payload (never include secrets).
        ip_address: Client IP extracted from request headers.
    """
    # Import lazily to avoid circular imports at module load time
    from app.models.audit_log import AuditLog  # noqa: PLC0415

    uid: uuid.UUID | None = None
    if user_id is not None:
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id

    entry = AuditLog(
        user_id=uid,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
    )
    try:
        db.add(entry)
        await db.flush()  # Flush without committing; caller commits the transaction.
    except Exception as exc:  # noqa: BLE001
        # Audit log failures must never crash the endpoint.
        logger.warning(
            "audit_log.write_failed",
            action=action,
            resource=resource,
            error=str(exc),
        )
