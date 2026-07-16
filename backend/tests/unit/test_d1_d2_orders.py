"""
Tests for OANDA forex order service (D-1) and kill-switch (D-2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest


def _token(user_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", email: str = "admin@test.com") -> str:
    from app.auth.jwt import create_access_token  # noqa: PLC0415

    return create_access_token({"sub": user_id, "email": email, "role": "trader"})


def _auth(user_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", email: str = "admin@test.com") -> dict:
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


# ────────────────────────────────────────────────────────────────────────────
# D-1 · OANDA Order Service
# ────────────────────────────────────────────────────────────────────────────


class TestOANDAOrderRequest:
    def test_buy_units_are_positive(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        req = OANDAOrderRequest(user_id="u1", symbol="EUR_USD", side="buy", order_type="market", units=10000)
        assert req.units > 0

    def test_sell_units_are_negative(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        req = OANDAOrderRequest(user_id="u1", symbol="EUR_USD", side="sell", order_type="market", units=10000)
        assert req.units < 0

    def test_limit_order_requires_price(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        with pytest.raises(ValueError, match="price is required"):
            OANDAOrderRequest(user_id="u1", symbol="EUR_USD", side="buy", order_type="limit", units=1000)

    def test_invalid_side_raises(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        with pytest.raises(ValueError, match="Invalid side"):
            OANDAOrderRequest(user_id="u1", symbol="EUR_USD", side="long", order_type="market", units=1000)

    def test_zero_units_raises(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        with pytest.raises(ValueError, match="units must be positive"):
            OANDAOrderRequest(user_id="u1", symbol="EUR_USD", side="buy", order_type="market", units=0)

    def test_symbol_normalisation(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        req = OANDAOrderRequest(user_id="u1", symbol="EUR/USD", side="buy", order_type="market", units=1000)
        assert req.instrument == "EUR_USD"

    def test_eurusd_no_separator_normalised(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest

        req = OANDAOrderRequest(user_id="u1", symbol="EURUSD", side="buy", order_type="market", units=1000)
        assert req.instrument == "EUR_USD"


class TestPlaceForexOrderSimulated:
    """When OANDA credentials are absent, place_forex_order returns a simulated fill."""

    @pytest.mark.asyncio
    async def test_simulated_fill_returns_filled_status(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest, place_forex_order

        with patch("app.services.orders.oanda_order_service.settings") as mock_settings:
            mock_settings.oanda_api_key = ""
            mock_settings.oanda_account_id = ""

            req = OANDAOrderRequest(
                user_id="u1", symbol="EUR_USD", side="buy", order_type="market", units=10000
            )
            result = await place_forex_order(req)

        assert result.status == "filled"
        assert result.instrument == "EUR_USD"
        assert result.units == 10000
        assert result.fill_price is not None

    @pytest.mark.asyncio
    async def test_simulated_fill_uses_limit_price(self):
        from app.services.orders.oanda_order_service import OANDAOrderRequest, place_forex_order

        with patch("app.services.orders.oanda_order_service.settings") as mock_settings:
            mock_settings.oanda_api_key = ""
            mock_settings.oanda_account_id = ""

            req = OANDAOrderRequest(
                user_id="u1",
                symbol="EUR_USD",
                side="buy",
                order_type="limit",
                units=1000,
                price=1.0850,
            )
            result = await place_forex_order(req)

        assert result.fill_price == 1.0850


class TestCancelForexOrderSimulated:
    @pytest.mark.asyncio
    async def test_simulated_cancel_returns_true(self):
        from app.services.orders.oanda_order_service import cancel_forex_order

        with patch("app.services.orders.oanda_order_service.settings") as mock_settings:
            mock_settings.oanda_api_key = ""
            mock_settings.oanda_account_id = ""

            result = await cancel_forex_order("fake-order-id")

        assert result is True


class TestGetOpenForexOrdersSimulated:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unconfigured(self):
        from app.services.orders.oanda_order_service import get_open_forex_orders

        with patch("app.services.orders.oanda_order_service.settings") as mock_settings:
            mock_settings.oanda_api_key = ""
            mock_settings.oanda_account_id = ""

            result = await get_open_forex_orders()

        assert result == []


# ────────────────────────────────────────────────────────────────────────────
# D-2 · Kill-Switch Service
# ────────────────────────────────────────────────────────────────────────────


class TestKillSwitchService:
    @pytest.mark.asyncio
    async def test_is_inactive_by_default(self):
        """When Redis has no key, kill-switch reports inactive."""
        from app.services.kill_switch import KillSwitch

        ks = KillSwitch()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        ks._redis = mock_redis

        assert not await ks.is_active()

    @pytest.mark.asyncio
    async def test_is_active_when_key_is_one(self):
        from app.services.kill_switch import KillSwitch

        ks = KillSwitch()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")
        ks._redis = mock_redis

        assert await ks.is_active()

    @pytest.mark.asyncio
    async def test_enable_sets_key(self):
        from app.services.kill_switch import KillSwitch

        ks = KillSwitch()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        ks._redis = mock_redis

        await ks.enable()
        mock_redis.set.assert_called_once_with("kill_switch:orders", "1")

    @pytest.mark.asyncio
    async def test_disable_deletes_key(self):
        from app.services.kill_switch import KillSwitch

        ks = KillSwitch()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        ks._redis = mock_redis

        await ks.disable()
        mock_redis.delete.assert_called_once_with("kill_switch:orders")

    @pytest.mark.asyncio
    async def test_fail_open_when_redis_unavailable(self):
        """If Redis is down, kill-switch reports inactive (fail-open)."""
        from app.services.kill_switch import KillSwitch

        ks = KillSwitch()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))
        ks._redis = mock_redis

        # Should return False (fail-open), not raise
        assert not await ks.is_active()


# ────────────────────────────────────────────────────────────────────────────
# D-2 · Admin API endpoints
# ────────────────────────────────────────────────────────────────────────────


class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_get_status_inactive(self):
        """GET /admin/kill-switch returns active=false when Redis has no key.
        admin_emails is left empty so any authenticated user is treated as admin.
        """
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with (
                patch("app.api.v1.admin._kill_switch.is_active", AsyncMock(return_value=False)),
                patch.object(__import__("app.api.v1.admin", fromlist=["settings"]).settings, "admin_emails", []),
            ):
                resp = await ac.get(
                    "/api/v1/admin/kill-switch",
                    headers=_auth(),
                )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_enable_kill_switch(self):
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with (
                patch("app.api.v1.admin._kill_switch.enable", AsyncMock()),
                patch("app.api.v1.admin._kill_switch.is_active", AsyncMock(return_value=True)),
                patch.object(__import__("app.api.v1.admin", fromlist=["settings"]).settings, "admin_emails", []),
            ):
                resp = await ac.post(
                    "/api/v1/admin/kill-switch/enable",
                    headers=_auth(),
                )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    @pytest.mark.asyncio
    async def test_disable_kill_switch(self):
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with (
                patch("app.api.v1.admin._kill_switch.disable", AsyncMock()),
                patch("app.api.v1.admin._kill_switch.is_active", AsyncMock(return_value=False)),
                patch.object(__import__("app.api.v1.admin", fromlist=["settings"]).settings, "admin_emails", []),
            ):
                resp = await ac.post(
                    "/api/v1/admin/kill-switch/disable",
                    headers=_auth(),
                )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self):
        """User whose email is not in admin_emails list gets 403."""
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with (
                patch("app.api.v1.admin._kill_switch.is_active", AsyncMock(return_value=False)),
                patch.object(
                    __import__("app.api.v1.admin", fromlist=["settings"]).settings,
                    "admin_emails",
                    ["other@test.com"],
                ),
            ):
                resp = await ac.get(
                    "/api/v1/admin/kill-switch",
                    headers=_auth(email="notadmin@test.com"),
                )
        assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────────────────
# D-2 · Kill-switch blocks orders.py endpoint
# ────────────────────────────────────────────────────────────────────────────


class TestOrdersKillSwitchIntegration:
    @pytest.mark.asyncio
    async def test_place_order_blocked_by_kill_switch(self):
        """POST /orders returns 503 when kill-switch is active."""
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            with patch("app.api.v1.orders._kill_switch.is_active", AsyncMock(return_value=True)):
                resp = await ac.post(
                    "/api/v1/orders",
                    json={
                        "symbol": "AAPL",
                        "side": "buy",
                        "order_type": "market",
                        "quantity": 10,
                    },
                    headers=_auth(),
                )
        assert resp.status_code == 503
        assert "kill-switch" in resp.json()["detail"].lower()
