"""
Unit tests for the Order Management Service.

Tests the service logic with Alpaca keys unavailable (simulation mode),
and validates OrderRequest validation rules.
"""

from __future__ import annotations

import pytest

# ─── OrderRequest validation ──────────────────────────────────────────────────


class TestOrderRequest:
    def test_valid_market_buy(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        req = OrderRequest(
            user_id="user-1",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
        )
        assert req.symbol == "AAPL"
        assert req.side == "buy"
        assert req.quantity == 10.0
        assert len(req.client_order_id) == 36  # UUID format

    def test_symbol_uppercased(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        req = OrderRequest(user_id="u", symbol="aapl", side="sell", order_type="market", quantity=5)
        assert req.symbol == "AAPL"

    def test_invalid_side_raises(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        with pytest.raises(ValueError, match="Invalid side"):
            OrderRequest(user_id="u", symbol="X", side="long", order_type="market", quantity=1)

    def test_zero_quantity_raises(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        with pytest.raises(ValueError, match="Quantity must be positive"):
            OrderRequest(user_id="u", symbol="X", side="buy", order_type="market", quantity=0)

    def test_limit_order_without_price_raises(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        with pytest.raises(ValueError, match="limit_price required"):
            OrderRequest(
                user_id="u",
                symbol="X",
                side="buy",
                order_type="limit",
                quantity=10,
                limit_price=None,
            )

    def test_limit_order_with_price_valid(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=5,
            limit_price=150.0,
        )
        assert req.limit_price == 150.0


# ─── place_order simulation mode ─────────────────────────────────────────────


class TestPlaceOrderSimulation:
    @pytest.mark.asyncio
    async def test_simulated_fill_when_no_alpaca_keys(self) -> None:
        """Without Alpaca keys, order is simulated as immediately filled."""
        from app.services.orders.service import OrderRequest, place_order  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
        )
        result = await place_order(req)
        assert result.symbol == "AAPL"
        assert result.status == "filled"
        assert result.filled_qty == 10.0
        assert result.order_id  # non-empty

    @pytest.mark.asyncio
    async def test_simulated_cancel_returns_true(self) -> None:
        from app.services.orders.service import cancel_order  # noqa: PLC0415

        success = await cancel_order("fake-broker-id")
        assert success is True

    @pytest.mark.asyncio
    async def test_simulated_get_open_returns_empty(self) -> None:
        from app.services.orders.service import get_open_orders  # noqa: PLC0415

        orders = await get_open_orders()
        assert orders == []

    @pytest.mark.asyncio
    async def test_simulated_limit_order_uses_limit_price(self) -> None:
        from app.services.orders.service import OrderRequest, place_order  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="MSFT",
            side="buy",
            order_type="limit",
            quantity=5,
            limit_price=380.0,
        )
        result = await place_order(req)
        assert result.filled_avg_price == 380.0
        assert result.limit_price == 380.0
