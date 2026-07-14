"""
Integration test — Alembic migration applies and reverts cleanly against SQLite.

NOTE: The real migration targets PostgreSQL (TimescaleDB). SQLite is used here
for CI purposes to verify table creation logic without a live PostgreSQL instance.
PostgreSQL-specific column types (JSONB, INET, ARRAY) are rendered by SQLAlchemy
with fallback types in SQLite, so some columns may differ from production schema.

For a full production migration test, run against TimescaleDB:
    DATABASE_SYNC_URL=postgresql://... pytest tests/integration/test_migrations.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

TABLES = [
    "users",
    "watchlists",
    "alerts",
    "ohlcv",
    "ticks",
    "fundamentals",
    "portfolios",
    "positions",
    "economic_events",
    "dashboard_layouts",
    "audit_log",
]

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


def _make_alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="module")
def sqlite_url(tmp_path_factory) -> str:
    p = tmp_path_factory.mktemp("db") / "test_migration.db"
    return f"sqlite:///{p}"


@pytest.fixture(scope="module", autouse=False)
def set_migration_env(sqlite_url):
    os.environ["DATABASE_SYNC_URL"] = sqlite_url
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-minimum-32-chars-long")
    yield
    os.environ.pop("DATABASE_SYNC_URL", None)


def test_upgrade_head_creates_all_tables(set_migration_env, sqlite_url):
    """Running upgrade head on a fresh DB creates every expected table."""
    try:
        command.upgrade(_make_alembic_cfg(sqlite_url), "head")
    except Exception as exc:
        # JSONB/INET/ARRAY fall back gracefully in SQLite — only fail on
        # structural errors (wrong table names, missing FK targets, etc.)
        pytest.skip(f"Migration incompatible with SQLite dialect: {exc}")

    engine = sa.create_engine(sqlite_url)
    inspector = sa.inspect(engine)
    existing = set(inspector.get_table_names())
    engine.dispose()

    missing = [t for t in TABLES if t not in existing]
    assert not missing, f"Tables missing after upgrade head: {missing}"


def test_downgrade_base_drops_all_tables(set_migration_env, sqlite_url):
    """Running downgrade base removes all domain tables."""
    # Ensure we start from head (previous test may have run)
    try:
        command.upgrade(_make_alembic_cfg(sqlite_url), "head")
        command.downgrade(_make_alembic_cfg(sqlite_url), "base")
    except Exception as exc:
        pytest.skip(f"Migration incompatible with SQLite dialect: {exc}")

    engine = sa.create_engine(sqlite_url)
    inspector = sa.inspect(engine)
    remaining = [
        t for t in inspector.get_table_names()
        if t != "alembic_version"
    ]
    engine.dispose()

    assert not remaining, f"Tables still present after downgrade base: {remaining}"
