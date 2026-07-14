"""
Unit tests for /workspaces CRUD endpoints (ST-T).
"""

from __future__ import annotations

import pytest
from app.api.v1.workspaces import _MEMBERS, _STORE
from app.main import app
from httpx import ASGITransport, AsyncClient

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _token(user_id: str = "user-ws-1") -> str:
    from app.auth.jwt import create_access_token
    return create_access_token({"sub": user_id, "email": f"{user_id}@t.com", "role": "trader"})


def _auth(user_id: str = "user-ws-1") -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


@pytest.fixture(autouse=True)
def clear_store():
    """Isolate in-memory store between tests."""
    _STORE.clear()
    _MEMBERS.clear()
    yield
    _STORE.clear()
    _MEMBERS.clear()


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_workspace_returns_201_with_owner():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Alpha Squad"},
            headers=_auth("owner-1"),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alpha Squad"
    assert data["owner_id"] == "owner-1"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_list_workspaces_returns_own_workspace():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        # Create
        await ac.post(
            "/api/v1/workspaces",
            json={"name": "My WS"},
            headers=_auth("lister-1"),
        )
        # List
        resp = await ac.get("/api/v1/workspaces", headers=_auth("lister-1"))
    assert resp.status_code == 200
    names = [w["name"] for w in resp.json()]
    assert "My WS" in names


@pytest.mark.anyio
async def test_delete_own_workspace_returns_204():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "To Delete"},
            headers=_auth("del-owner"),
        )
        ws_id = create.json()["id"]
        resp = await ac.delete(f"/api/v1/workspaces/{ws_id}", headers=_auth("del-owner"))
    assert resp.status_code == 204
    assert ws_id not in _STORE


@pytest.mark.anyio
async def test_delete_other_users_workspace_returns_403():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Protected"},
            headers=_auth("real-owner"),
        )
        ws_id = create.json()["id"]
        resp = await ac.delete(f"/api/v1/workspaces/{ws_id}", headers=_auth("intruder"))
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_delete_nonexistent_workspace_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.delete(
            "/api/v1/workspaces/00000000-0000-0000-0000-000000000000",
            headers=_auth("any-user"),
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_invite_member_and_list_members():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Team WS"},
            headers=_auth("team-owner"),
        )
        ws_id = create.json()["id"]

        invite = await ac.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": "new-member-99", "role": "member"},
            headers=_auth("team-owner"),
        )
        assert invite.status_code == 201
        assert invite.json()["user_id"] == "new-member-99"

        members_resp = await ac.get(
            f"/api/v1/workspaces/{ws_id}/members",
            headers=_auth("team-owner"),
        )
        assert members_resp.status_code == 200
        user_ids = [m["user_id"] for m in members_resp.json()]
        assert "new-member-99" in user_ids


@pytest.mark.anyio
async def test_list_includes_workspace_user_is_member_of():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        create = await ac.post(
            "/api/v1/workspaces",
            json={"name": "Shared WS"},
            headers=_auth("ws-owner"),
        )
        ws_id = create.json()["id"]
        await ac.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": "guest-user"},
            headers=_auth("ws-owner"),
        )
        resp = await ac.get("/api/v1/workspaces", headers=_auth("guest-user"))
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert ws_id in ids
