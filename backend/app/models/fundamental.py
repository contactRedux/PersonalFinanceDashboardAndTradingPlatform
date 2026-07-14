"""
ORM model for fundamental data (refreshed daily).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Fundamental(Base):
    __tablename__ = "fundamentals"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    revenue_ttm: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    net_income_ttm: Mapped[Decimal | None] = mapped_column(Numeric(30, 2), nullable=True)
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    debt_equity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
