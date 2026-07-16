"""
ORM models for fundamentals data populated by the FMP adapter.

Tables:
  fundamentals         — core company snapshot (extended from original schema)
  insider_transactions — Form 4 insider buy/sell filings
  institutional_holders — 13-F top institutional positions
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Fundamental(Base):
    """
    Core company fundamental snapshot — refreshed daily via Celery task.
    Composite primary key (symbol, as_of_date) keeps history.
    """

    __tablename__ = "fundamentals"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Valuation
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    dcf_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)

    # Income statement (TTM)
    revenue_ttm: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    net_income_ttm: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # Balance sheet
    debt_equity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)

    # Per-share / yield
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    eps_ttm: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)

    # Company metadata
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    employees: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class InsiderTransaction(Base):
    """
    Individual insider buy/sell transaction (SEC Form 4 filing).
    Source: FMP /insider-trading endpoint.
    """

    __tablename__ = "insider_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    insider_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(10), nullable=True)   # P / S
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    shares_owned_after: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    sec_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class InstitutionalHolder(Base):
    """
    Top institutional holder from 13-F filing.
    Source: FMP /institutional-ownership endpoint.
    """

    __tablename__ = "institutional_holders"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    holder: Mapped[str | None] = mapped_column(String(300), nullable=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    pct_portfolio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    change: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)   # shares delta

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
