"""
Integration tests for health and auth REST endpoints.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_login_with_invalid_credentials(client):
    """Login should return 422 (validation) if email is malformed."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "password"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    """Any /api/v1 endpoint except /auth/* requires Bearer token."""
    response = await client.get("/api/v1/market/quotes?symbols=AAPL")
    # 403 (no token) or 422
    assert response.status_code in (401, 403, 422)
