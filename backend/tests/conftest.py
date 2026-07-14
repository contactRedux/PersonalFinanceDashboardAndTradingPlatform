"""
Backend test configuration and shared fixtures.
"""

from __future__ import annotations

import os
import sys

# Add the monorepo root to sys.path so tests can import ml.* and backtesting.*
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture
async def client():
    """Async test client for FastAPI app (no real DB/Redis needed for unit tests)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
