"""Add fundamentals extensions: new columns + insider_transactions + institutional_holders tables.

Revision ID: 0006_add_fundamentals_fmp
Revises: 0005
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_fundamentals_fmp"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Extend fundamentals table with new FMP columns ────────────────────────
    with op.batch_alter_table("fundamentals") as batch_op:
        batch_op.add_column(sa.Column("dcf_value", sa.Numeric(15, 4), nullable=True))
        batch_op.add_column(sa.Column("operating_margin", sa.Numeric(8, 4), nullable=True))
        batch_op.add_column(sa.Column("current_ratio", sa.Numeric(15, 4), nullable=True))
        batch_op.add_column(sa.Column("eps_ttm", sa.Numeric(15, 4), nullable=True))
        batch_op.add_column(sa.Column("company_name", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("description", sa.String(2000), nullable=True))
        batch_op.add_column(sa.Column("exchange", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("website", sa.String(300), nullable=True))
        batch_op.add_column(sa.Column("employees", sa.BigInteger(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            )
        )

    # ── insider_transactions ──────────────────────────────────────────────────
    op.create_table(
        "insider_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("insider_name", sa.String(200), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=True),
        sa.Column("shares", sa.Numeric(20, 2), nullable=True),
        sa.Column("price", sa.Numeric(15, 4), nullable=True),
        sa.Column("value", sa.Numeric(30, 2), nullable=True),
        sa.Column("shares_owned_after", sa.Numeric(20, 2), nullable=True),
        sa.Column("sec_link", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_insider_transactions_symbol",
        "insider_transactions",
        ["symbol"],
        unique=False,
    )

    # ── institutional_holders ────────────────────────────────────────────────
    op.create_table(
        "institutional_holders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("holder", sa.String(300), nullable=True),
        sa.Column("shares", sa.Numeric(20, 2), nullable=True),
        sa.Column("value", sa.Numeric(30, 2), nullable=True),
        sa.Column("pct_portfolio", sa.Numeric(8, 4), nullable=True),
        sa.Column("change", sa.Numeric(20, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_institutional_holders_symbol",
        "institutional_holders",
        ["symbol"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_institutional_holders_symbol", table_name="institutional_holders")
    op.drop_table("institutional_holders")

    op.drop_index("ix_insider_transactions_symbol", table_name="insider_transactions")
    op.drop_table("insider_transactions")

    with op.batch_alter_table("fundamentals") as batch_op:
        for col in [
            "dcf_value", "operating_margin", "current_ratio", "eps_ttm",
            "company_name", "description", "exchange", "website", "employees", "updated_at",
        ]:
            batch_op.drop_column(col)
