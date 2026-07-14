"""
Unit tests for POST /portfolio/import (ST-S).
"""

from __future__ import annotations

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_token() -> str:
    from app.auth.jwt import create_access_token
    return create_access_token({"sub": "user-import-test", "email": "t@t.com", "role": "trader"})


def _csv_file(content: str) -> tuple:
    return ("file", ("positions.csv", content.encode(), "text/csv"))


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_valid_csv_imports_successfully():
    token = _make_token()
    csv_body = "symbol,quantity,avg_price\nAAPL,10,150.00\nMSFT,5,300.00\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    symbols = [p["symbol"] for p in data["positions"]]
    assert "AAPL" in symbols
    assert "MSFT" in symbols


@pytest.mark.anyio
async def test_missing_symbol_column_returns_422():
    token = _make_token()
    csv_body = "ticker,quantity,avg_price\nAAPL,10,150.00\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_negative_quantity_returns_422():
    token = _make_token()
    csv_body = "symbol,quantity,avg_price\nAAPL,-5,150.00\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["rows"][0]["row"] == 2


@pytest.mark.anyio
async def test_empty_csv_returns_imported_zero():
    token = _make_token()
    csv_body = "symbol,quantity,avg_price\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 0


@pytest.mark.anyio
async def test_zero_avg_price_returns_422():
    token = _make_token()
    csv_body = "symbol,quantity,avg_price\nAAPL,10,0\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_optional_date_opened_accepted():
    token = _make_token()
    csv_body = "symbol,quantity,avg_price,date_opened\nNVDA,2,500.00,2024-01-15\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            headers={"Authorization": f"Bearer {token}"},
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["positions"][0].get("date_opened") == "2024-01-15"


@pytest.mark.anyio
async def test_unauthenticated_returns_403_or_401():
    csv_body = "symbol,quantity,avg_price\nAAPL,1,100\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import",
            files=[_csv_file(csv_body)],
        )
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_import_csv_dedup_updates_quantity_and_avg_price():
    """
    Import CSV with an existing symbol → quantity is summed and avg_price is
    recomputed as a weighted average.
    """
    token = _make_token()
    # First import: 10 AAPL @ 150.00
    csv1 = "symbol,quantity,avg_price\nAAPL,10,150.00\n"
    # Second import: 10 AAPL @ 200.00  → combined: qty=20, avg=(1500+2000)/20=175.00
    csv2 = "symbol,quantity,avg_price\nAAPL,10,200.00\n"

    # Use a unique token so the in-memory store is isolated per user sub
    import secrets  # noqa: PLC0415
    unique_sub = f"dedup-test-{secrets.token_hex(4)}"
    from app.auth.jwt import create_access_token  # noqa: PLC0415
    unique_token = create_access_token({"sub": unique_sub, "email": "d@d.com", "role": "trader"})
    headers = {"Authorization": f"Bearer {unique_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        r1 = await ac.post(
            "/api/v1/portfolio/import",
            headers=headers,
            files=[_csv_file(csv1)],
        )
        assert r1.status_code == 200

        r2 = await ac.post(
            "/api/v1/portfolio/import",
            headers=headers,
            files=[_csv_file(csv2)],
        )
        assert r2.status_code == 200
        data = r2.json()
        assert data["imported"] == 1

    # Check in-memory store for the combined result
    from app.api.v1.portfolio import _IMPORTED_POSITIONS  # noqa: PLC0415
    store = _IMPORTED_POSITIONS.get(unique_sub, [])
    aapl = next((p for p in store if p["symbol"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["quantity"] == 20.0
    assert abs(aapl["avg_price"] - 175.0) < 0.01


@pytest.mark.anyio
async def test_import_broker_returns_501():
    """POST /portfolio/import/broker returns HTTP 501 with the stub message."""
    token = _make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        resp = await ac.post(
            "/api/v1/portfolio/import/broker",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 501
    body = resp.json()
    assert body["status"] == "not_implemented"
    assert "alpaca" in body["supported_brokers"]
