"""
SQLAlchemy ORM model for orders table.

Tracks order lifecycle: pending → submitted → filled / cancelled / rejected.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    client_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Order fields
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False, default="equity")
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy | sell
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)  # market | limit | stop
    time_in_force: Mapped[str] = mapped_column(String(10), nullable=False, default="day")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | submitted | partially_filled | filled | cancelled | rejected
    filled_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filled_avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} symbol={self.symbol} side={self.side} "
            f"qty={self.quantity} status={self.status}>"
        )
