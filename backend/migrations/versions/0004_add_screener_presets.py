"""add_screener_presets

Revision ID: 0004_add_screener_presets
Revises: 0003_add_strategy_configs
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_screener_presets"
down_revision: str | None = "0003_add_strategy_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screener_presets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_screener_presets_user_id"), "screener_presets", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_screener_presets_user_id"), table_name="screener_presets")
    op.drop_table("screener_presets")
