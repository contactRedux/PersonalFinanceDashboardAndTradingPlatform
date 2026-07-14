"""add_strategy_configs

Revision ID: 0003_add_strategy_configs
Revises: 0002_add_workspaces
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_add_strategy_configs"
down_revision: str | None = "0002_add_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("strategy_type", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_strategy_configs_user_id"), "strategy_configs", ["user_id"], unique=False
    )

    # Also add layout + updated_at columns to workspaces (ORM model has them but DDL didn't)
    op.add_column(
        "workspaces",
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add acknowledged_at to alerts (ST-3 — required by new alert logic)
    op.add_column(
        "alerts",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("workspaces", "updated_at")
    op.drop_column("workspaces", "layout")
    op.drop_index(op.f("ix_strategy_configs_user_id"), table_name="strategy_configs")
    op.drop_table("strategy_configs")
