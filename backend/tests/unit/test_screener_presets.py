"""
Unit tests — Screener Presets DB Persistence (ST-AA).
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.auth.jwt import create_access_token
from app.dependencies import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


_DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def _auth(user_id: str = _DEFAULT_USER_ID) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "email": "t@t.com", "role": "trader"})
    return {"Authorization": f"Bearer {token}"}


def _mock_db_session():
    """Return a mock AsyncSession that supports add/commit/refresh/execute."""
    db = MagicMock(spec=AsyncSession)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _override_get_db(db: AsyncSession):
    """Create a FastAPI dependency override that yields the mock session."""
    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        yield db
    return _get_db_override


# ─── Test 1: Create preset → GET list shows it ────────────────────────────────

@pytest.mark.anyio
async def test_create_preset_appears_in_list():
    """POST /screener/presets creates a preset; GET /screener/presets returns it."""
    preset_id = uuid.uuid4()
    preset_name = "My Test Screen"
    preset_conditions = [{"field": "rsi_14", "op": "lt", "value": 30}]

    from app.models.screener_preset import ScreenerPreset  # noqa: PLC0415

    from datetime import UTC, datetime  # noqa: PLC0415

    saved = ScreenerPreset(
        id=preset_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name=preset_name,
        conditions=preset_conditions,
    )
    saved.created_at = datetime(2025, 1, 1, tzinfo=UTC)

    db = _mock_db_session()

    # db.add sets id/created_at so refresh sees them
    def _add(obj: object) -> None:
        if isinstance(obj, ScreenerPreset):
            obj.id = preset_id
            obj.created_at = datetime(2025, 1, 1, tzinfo=UTC)

    db.add = MagicMock(side_effect=_add)

    # execute returns saved preset on SELECT
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [saved]
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            post_resp = await ac.post(
                "/api/v1/screener/presets",
                json={"name": preset_name, "conditions": preset_conditions},
                headers=_auth(),
            )
            assert post_resp.status_code == 201, post_resp.text
            body = post_resp.json()
            assert body["name"] == preset_name
            assert body["conditions"] == preset_conditions
            assert body["is_user_preset"] is True

            get_resp = await ac.get("/api/v1/screener/presets", headers=_auth())
            assert get_resp.status_code == 200
            presets = get_resp.json()["presets"]
            user_presets = [p for p in presets if p.get("is_user_preset")]
            assert len(user_presets) >= 1
            assert user_presets[0]["name"] == preset_name
    finally:
        app.dependency_overrides.pop(get_db, None)


# ─── Test 2: Delete own preset → gone from list ───────────────────────────────

@pytest.mark.anyio
async def test_delete_own_preset_removes_it():
    """DELETE /screener/presets/{id} removes the preset from the list."""
    user_id_str = "00000000-0000-0000-0000-000000000002"
    preset_id = uuid.uuid4()

    from app.models.screener_preset import ScreenerPreset  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    preset = ScreenerPreset(
        id=preset_id,
        user_id=uuid.UUID(user_id_str),
        name="To Delete",
        conditions=[],
    )
    preset.created_at = datetime(2025, 1, 1, tzinfo=UTC)

    db = _mock_db_session()
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = preset
    select_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=select_result)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            del_resp = await ac.delete(
                f"/api/v1/screener/presets/{preset_id}",
                headers=_auth(user_id_str),
            )
            assert del_resp.status_code == 204

            get_resp = await ac.get("/api/v1/screener/presets", headers=_auth(user_id_str))
            assert get_resp.status_code == 200
            user_presets = [p for p in get_resp.json()["presets"] if p.get("is_user_preset")]
            assert len(user_presets) == 0
    finally:
        app.dependency_overrides.pop(get_db, None)


# ─── Test 3: Delete other user's preset → 403 ────────────────────────────────

@pytest.mark.anyio
async def test_delete_other_users_preset_returns_403():
    """DELETE /screener/presets/{id} returns 403 when the preset belongs to another user."""
    owner_id = "00000000-0000-0000-0000-000000000003"
    attacker_id = "00000000-0000-0000-0000-000000000004"
    preset_id = uuid.uuid4()

    from app.models.screener_preset import ScreenerPreset  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    preset = ScreenerPreset(
        id=preset_id,
        user_id=uuid.UUID(owner_id),
        name="Owner's Preset",
        conditions=[],
    )
    preset.created_at = datetime(2025, 1, 1, tzinfo=UTC)

    db = _mock_db_session()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = preset
    db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            resp = await ac.delete(
                f"/api/v1/screener/presets/{preset_id}",
                headers=_auth(attacker_id),
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
