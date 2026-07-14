"""
ORM models for OHLCV bars and tick data (TimescaleDB hypertables).
The hypertable setup is done in a post-migration SQL script.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OHLCV(Base):
    """
    TimescaleDB hypertable — one row per (symbol, timeframe, time) bar.
    Partitioned by time with 1-day chunks for minute data.
    """
    __tablename__ = "ohlcv"
    __table_args__ = (
        UniqueConstraint("time", "symbol", "timeframe", name="uq_ohlcv_time_symbol_timeframe"),
        Index("ix_ohlcv_symbol_timeframe_time", "symbol", "timeframe", "time"),
    )

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), primary_key=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False, default="equity")
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)


class Tick(Base):
    """
    TimescaleDB hypertable — individual trade prints.
    Partitioned by time with 1-hour chunks.
    """
    __tablename__ = "ticks"
    __table_args__ = (
        Index("ix_ticks_symbol_time", "symbol", "time"),
    )

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    side: Mapped[str | None] = mapped_column(String(1), nullable=True)   # B / S / U
    exchange: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
