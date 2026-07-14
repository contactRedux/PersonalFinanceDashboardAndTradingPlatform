"""
ORM model for the audit log.
All auth events, trade mutations, and config changes are recorded here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, Sequence, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_audit_seq = Sequence("audit_log_id_seq")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, _audit_seq, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(200), nullable=False)
    # JSON is portable (works on SQLite in tests); migrations use JSONB on Postgres
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # INET is Postgres-only; String(45) covers IPv4 + IPv6 and works everywhere
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
