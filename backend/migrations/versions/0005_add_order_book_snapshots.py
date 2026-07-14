"""Add order_book_snapshots hypertable.

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004_add_screener_presets"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS order_book_snapshots (
            time        TIMESTAMPTZ     NOT NULL,
            symbol      TEXT            NOT NULL,
            bids        JSONB           NOT NULL DEFAULT '[]',
            asks        JSONB           NOT NULL DEFAULT '[]',
            mid_price   NUMERIC(18, 8),
            spread      NUMERIC(18, 8)
        );
    """)
    # Try to create hypertable (no-op if TimescaleDB not available)
    op.execute("""
        DO $$
        BEGIN
            PERFORM create_hypertable(
                'order_book_snapshots', 'time',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            );
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_obs_symbol_time
            ON order_book_snapshots (symbol, time DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_book_snapshots;")
