"""
Backend test configuration and shared fixtures.
"""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture
async def client():
    """Async test client for FastAPI app (no real DB/Redis needed for unit tests)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
