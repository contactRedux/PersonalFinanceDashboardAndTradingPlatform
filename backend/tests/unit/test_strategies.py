"""
Unit tests for /strategies CRUD endpoints.

Uses aiosqlite (in-memory) via the test DATABASE_URL.
"""

from __future__ import annotations

import pytest
from app.database import Base, engine
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects import sqlite


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _token(user_id: str = "11111111-1111-1111-1111-111111111111") -> str:
    from app.auth.jwt import create_access_token  # noqa: PLC0415
    return create_access_token({"sub": user_id, "email": f"{user_id}@t.com", "role": "trader"})


def _auth(user_id: str = "11111111-1111-1111-1111-111111111111") -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


_VALID_CONFIG = {"nodes": [{"id": "1", "type": "entry"}], "edges": []}


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables in the test SQLite DB before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_strategy_full_crud():
    """Happy path: POST → GET list → GET by ID → DELETE → GET list empty."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        uid = "11111111-1111-1111-1111-111111111111"

        # Create
        resp = await ac.post(
            "/api/v1/strategies",
            json={"name": "My MA Cross", "description": "Fast/slow cross", "config": _VALID_CONFIG},
            headers=_auth(uid),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My MA Cross"
        assert data["description"] == "Fast/slow cross"
        assert data["user_id"] == uid
        strategy_id = data["id"]

        # List
        list_resp = await ac.get("/api/v1/strategies", headers=_auth(uid))
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["count"] == 1
        assert body["strategies"][0]["id"] == strategy_id

        # Get by ID
        get_resp = await ac.get(f"/api/v1/strategies/{strategy_id}", headers=_auth(uid))
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == strategy_id

        # Delete
        del_resp = await ac.delete(f"/api/v1/strategies/{strategy_id}", headers=_auth(uid))
        assert del_resp.status_code == 204

        # List now empty
        list_resp2 = await ac.get("/api/v1/strategies", headers=_auth(uid))
        assert list_resp2.json()["count"] == 0


@pytest.mark.anyio
async def test_get_nonexistent_strategy_returns_404():
    """Getting or deleting a non-existent strategy ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.get(f"/api/v1/strategies/{fake_id}", headers=_auth())
        assert resp.status_code == 404

        del_resp = await ac.delete(f"/api/v1/strategies/{fake_id}", headers=_auth())
        assert del_resp.status_code == 404


@pytest.mark.anyio
async def test_strategy_isolation_between_users():
    """User A cannot see or delete User B's strategy."""
    uid_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    uid_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        # User A creates strategy
        resp = await ac.post(
            "/api/v1/strategies",
            json={"name": "A's strategy", "config": _VALID_CONFIG},
            headers=_auth(uid_a),
        )
        sid = resp.json()["id"]

        # User B cannot get it
        assert (await ac.get(f"/api/v1/strategies/{sid}", headers=_auth(uid_b))).status_code == 404
        # User B cannot delete it
        assert (
            await ac.delete(f"/api/v1/strategies/{sid}", headers=_auth(uid_b))
        ).status_code == 404


@pytest.mark.anyio
async def test_create_strategy_invalid_config_returns_422():
    """Config without nodes/edges returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/strategies",
            json={"name": "Bad", "config": {"foo": "bar"}},
            headers=_auth(),
        )
        assert resp.status_code == 422
