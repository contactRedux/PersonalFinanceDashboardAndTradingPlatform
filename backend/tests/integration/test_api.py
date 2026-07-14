"""
Integration tests for health and auth REST endpoints.

These tests require a running application context (Redis connection).
They are skipped automatically when Redis is not available.
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
async def test_login_with_invalid_email(client):
    """Login should return 422 if email is malformed."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "password"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    """Any /api/v1 endpoint except /auth/* returns 401 without a token."""
    response = await client.get("/api/v1/market/quotes?symbols=AAPL")
    # HTTPBearer(auto_error=True) raises HTTP 403 when header is absent
    assert response.status_code in (401, 403)
