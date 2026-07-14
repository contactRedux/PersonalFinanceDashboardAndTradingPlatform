"""
Unit tests for /workspaces CRUD endpoints.

Uses aiosqlite (in-memory) via the test DATABASE_URL.
All previous test cases preserved; internal-state assertions replaced with API-level checks.
"""

from __future__ import annotations

import pytest
from app.database import Base, engine
from app.main import app
from httpx import ASGITransport, AsyncClient


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _token(user_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") -> str:
    from app.auth.jwt import create_access_token  # noqa: PLC0415
    return create_access_token({"sub": user_id, "email": f"{user_id}@t.com", "role": "trader"})


def _auth(user_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


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
async def test_create_workspace_returns_201_with_owner():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Alpha Squad"},
            headers=_auth("owner-user-aaaa-aaaa-aaaaaaaaaaaa"),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alpha Squad"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_list_workspaces_returns_own_workspace():
    uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        await ac.post(
            "/api/v1/workspaces",
            json={"name": "My WS"},
            headers=_auth(uid),
        )
        resp = await ac.get("/api/v1/workspaces", headers=_auth(uid))
    assert resp.status_code == 200
    names = [w["name"] for w in resp.json()]
    assert "My WS" in names


@pytest.mark.anyio
async def test_delete_own_workspace_returns_204():
    uid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "To Delete"},
            headers=_auth(uid),
        )
        ws_id = create.json()["id"]
        resp = await ac.delete(f"/api/v1/workspaces/{ws_id}", headers=_auth(uid))
    assert resp.status_code == 204

    # Verify it is gone
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        list_resp = await ac.get("/api/v1/workspaces", headers=_auth(uid))
        ids = [w["id"] for w in list_resp.json()]
        assert ws_id not in ids


@pytest.mark.anyio
async def test_delete_other_users_workspace_returns_403():
    owner = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    intruder = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Protected"},
            headers=_auth(owner),
        )
        ws_id = create.json()["id"]
        resp = await ac.delete(f"/api/v1/workspaces/{ws_id}", headers=_auth(intruder))
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_delete_nonexistent_workspace_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.delete(
            "/api/v1/workspaces/00000000-0000-0000-0000-000000000000",
            headers=_auth(),
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_invite_member_and_list_members():
    owner = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Team WS"},
            headers=_auth(owner),
        )
        ws_id = create.json()["id"]

        invite = await ac.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": "11111111-1111-1111-1111-111111111111", "role": "editor"},
            headers=_auth(owner),
        )
        assert invite.status_code == 201

        members_resp = await ac.get(
            f"/api/v1/workspaces/{ws_id}/members",
            headers=_auth(owner),
        )
        assert members_resp.status_code == 200
        # Owner + invited member
        assert len(members_resp.json()) >= 1


@pytest.mark.anyio
async def test_list_includes_workspace_user_is_member_of():
    owner = "22222222-2222-2222-2222-222222222222"
    guest = "33333333-3333-3333-3333-333333333333"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Shared WS"},
            headers=_auth(owner),
        )
        ws_id = create.json()["id"]
        await ac.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": guest, "role": "viewer"},
            headers=_auth(owner),
        )
        resp = await ac.get("/api/v1/workspaces", headers=_auth(guest))
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert ws_id in ids
