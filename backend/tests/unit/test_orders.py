"""
Unit tests for the Order Management Service and portfolio/trades endpoint.

Tests the service logic with Alpaca keys unavailable (simulation mode),
validates OrderRequest validation rules, and covers the GET /portfolio/trades
route logic with a mocked database session.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

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


# ─── GET /portfolio/trades ────────────────────────────────────────────────────


class TestPortfolioTradesEndpoint:
    """Tests for the get_trades route function (mocked DB session)."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_filled_orders(self) -> None:
        """Empty orders table → trades: [], count: 0."""
        from app.api.v1.portfolio import get_trades  # noqa: PLC0415

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        current_user = {"sub": str(uuid.uuid4())}

        response = await get_trades(current_user=current_user, db=db, limit=200)
        assert response["trades"] == []
        assert response["count"] == 0

    @pytest.mark.asyncio
    async def test_returns_trade_records_for_filled_orders(self) -> None:
        """Filled orders are mapped to TradeRecord-compatible dicts."""
        from app.api.v1.portfolio import get_trades  # noqa: PLC0415
        from app.models.order import Order  # noqa: PLC0415

        now = datetime.now(UTC)
        order = Order(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            broker_order_id="broker-abc",
            client_order_id="client-abc",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            status="filled",
            filled_qty=10.0,
            filled_avg_price=185.50,
            submitted_at=now,
            filled_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [order]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        current_user = {"sub": str(order.user_id)}

        response = await get_trades(current_user=current_user, db=db, limit=200)
        assert response["count"] == 1
        trade = response["trades"][0]
        assert trade["id"] == "broker-abc"
        assert trade["symbol"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 10.0
        assert trade["entry_price"] == 185.50
        assert trade["exit_price"] is None  # single-leg orders have no exit price yet
        assert trade["pnl"] is None

    @pytest.mark.asyncio
    async def test_id_falls_back_to_order_uuid_when_no_broker_id(self) -> None:
        """When broker_order_id is None, id falls back to str(order.id)."""
        from app.api.v1.portfolio import get_trades  # noqa: PLC0415
        from app.models.order import Order  # noqa: PLC0415

        oid = uuid.uuid4()
        order = Order(
            id=oid,
            user_id=uuid.uuid4(),
            broker_order_id=None,
            client_order_id=None,
            symbol="MSFT",
            side="sell",
            order_type="market",
            quantity=5.0,
            status="filled",
            filled_qty=5.0,
            filled_avg_price=400.0,
            submitted_at=None,
            filled_at=None,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [order]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        current_user = {"sub": str(order.user_id)}

        response = await get_trades(current_user=current_user, db=db, limit=200)
        assert response["trades"][0]["id"] == str(oid)
        assert response["trades"][0]["entry_time"] is None
        assert response["trades"][0]["exit_time"] is None


# ─── Celery order_tasks — _process_order ─────────────────────────────────────


class TestSyncOpenOrders:
    """Tests for the _process_order helper inside order_tasks."""

    @pytest.mark.asyncio
    async def test_no_update_when_status_unchanged(self) -> None:
        """If the Alpaca order has the same status as the DB record, no write occurs."""
        from app.models.order import Order  # noqa: PLC0415
        from app.tasks.order_tasks import _process_order  # noqa: PLC0415

        order = Order(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            broker_order_id="broker-123",
            client_order_id=None,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=5.0,
            status="submitted",
            filled_qty=0.0,
        )
        alpaca_order = {"id": "broker-123", "status": "submitted", "filled_qty": 0}

        # Build a session mock that returns our order
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        publish_fn = AsyncMock()
        updated = await _process_order(session, alpaca_order, publish_fn)

        assert updated is False
        session.commit.assert_not_called()
        publish_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_publishes_update_on_fill(self) -> None:
        """When Alpaca reports 'filled', the DB is updated and publish_fn is called."""
        from app.models.order import Order  # noqa: PLC0415
        from app.tasks.order_tasks import _process_order  # noqa: PLC0415

        uid = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(),
            user_id=uid,
            broker_order_id="broker-456",
            client_order_id=None,
            symbol="NVDA",
            side="buy",
            order_type="market",
            quantity=10.0,
            status="submitted",
            filled_qty=0.0,
            filled_at=None,
        )
        alpaca_order = {
            "id": "broker-456",
            "status": "filled",
            "filled_qty": "10",
            "filled_avg_price": "498.50",
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        publish_fn = AsyncMock()
        updated = await _process_order(session, alpaca_order, publish_fn)

        assert updated is True
        assert order.status == "filled"
        assert order.filled_qty == 10.0
        assert order.filled_avg_price == 498.50
        session.commit.assert_called_once()
        publish_fn.assert_called_once()
        call_args = publish_fn.call_args
        assert call_args[0][0] == str(uid)
        assert call_args[0][1]["status"] == "filled"
        assert call_args[0][1]["symbol"] == "NVDA"

    @pytest.mark.asyncio
    async def test_returns_false_when_order_not_in_db(self) -> None:
        """Order in Alpaca but not in local DB → skip, no crash."""
        from app.tasks.order_tasks import _process_order  # noqa: PLC0415

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        publish_fn = AsyncMock()
        updated = await _process_order(
            session, {"id": "ghost-order", "status": "filled", "filled_qty": 1}, publish_fn
        )
        assert updated is False
        publish_fn.assert_not_called()


# ─── Bracket order validation ─────────────────────────────────────────────────


class TestBracketOrderRequest:
    def test_bracket_requires_take_profit_and_stop_loss(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        with pytest.raises(ValueError, match="take_profit_price and stop_loss_price required"):
            OrderRequest(
                user_id="u",
                symbol="AAPL",
                side="buy",
                order_type="market",
                quantity=10,
                order_class="bracket",
                take_profit_price=None,
                stop_loss_price=None,
            )

    def test_bracket_valid_with_both_prices(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10,
            order_class="bracket",
            take_profit_price=160.0,
            stop_loss_price=140.0,
        )
        assert req.order_class == "bracket"
        assert req.take_profit_price == 160.0
        assert req.stop_loss_price == 140.0

    def test_invalid_order_class_raises(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        with pytest.raises(ValueError, match="Invalid order_class"):
            OrderRequest(
                user_id="u",
                symbol="AAPL",
                side="buy",
                order_type="market",
                quantity=10,
                order_class="invalid",
            )

    def test_simple_order_class_is_default(self) -> None:
        from app.services.orders.service import OrderRequest  # noqa: PLC0415

        req = OrderRequest(user_id="u", symbol="AAPL", side="buy", order_type="market", quantity=5)
        assert req.order_class == "simple"


class TestBracketPlaceOrderSimulation:
    @pytest.mark.asyncio
    async def test_bracket_order_simulated_fill(self) -> None:
        """Bracket order falls back to simulated fill without Alpaca keys."""
        from app.services.orders.service import OrderRequest, place_order  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10,
            order_class="bracket",
            take_profit_price=160.0,
            stop_loss_price=140.0,
        )
        result = await place_order(req)
        assert result.status == "filled"
        assert result.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_oco_order_simulated_fill(self) -> None:
        """OCO order falls back to simulated fill without Alpaca keys."""
        from app.services.orders.service import OrderRequest, place_order  # noqa: PLC0415

        req = OrderRequest(
            user_id="u",
            symbol="MSFT",
            side="sell",
            order_type="limit",
            quantity=5,
            limit_price=400.0,
            order_class="oco",
            take_profit_price=420.0,
            stop_loss_price=380.0,
        )
        result = await place_order(req)
        assert result.status == "filled"


# ─── PATCH /orders/{id} — modify order ────────────────────────────────────────


class TestModifyOrderEndpoint:
    @pytest.mark.asyncio
    async def test_modify_returns_404_when_order_not_found(self) -> None:
        from app.api.v1.orders import (
            ModifyOrderRequest,  # noqa: PLC0415
            modify_order_endpoint,  # noqa: PLC0415
        )
        from fastapi import HTTPException  # noqa: PLC0415

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        current_user = {"sub": str(uuid.uuid4())}

        with pytest.raises(HTTPException) as exc_info:
            await modify_order_endpoint(
                order_id="nonexistent",
                body=ModifyOrderRequest(quantity=10),
                current_user=current_user,
                db=db,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_modify_409_when_order_filled(self) -> None:
        from app.api.v1.orders import (
            ModifyOrderRequest,  # noqa: PLC0415
            modify_order_endpoint,  # noqa: PLC0415
        )
        from app.models.order import Order  # noqa: PLC0415
        from fastapi import HTTPException  # noqa: PLC0415

        order = Order(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            broker_order_id="broker-xyz",
            client_order_id=None,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            status="filled",
            filled_qty=10.0,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        current_user = {"sub": str(order.user_id)}

        with pytest.raises(HTTPException) as exc_info:
            await modify_order_endpoint(
                order_id="broker-xyz",
                body=ModifyOrderRequest(quantity=20),
                current_user=current_user,
                db=db,
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_modify_updates_quantity_in_demo_mode(self) -> None:
        from app.api.v1.orders import (
            ModifyOrderRequest,  # noqa: PLC0415
            modify_order_endpoint,  # noqa: PLC0415
        )
        from app.models.order import Order  # noqa: PLC0415

        uid = uuid.uuid4()
        order = Order(
            id=uuid.uuid4(),
            user_id=uid,
            broker_order_id="broker-pending",
            client_order_id=None,
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=10.0,
            limit_price=150.0,
            status="accepted",
            filled_qty=0.0,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        current_user = {"sub": str(uid)}

        response = await modify_order_endpoint(
            order_id="broker-pending",
            body=ModifyOrderRequest(quantity=20.0, limit_price=155.0),
            current_user=current_user,
            db=db,
        )
        assert response.quantity == 20.0
        assert response.limit_price == 155.0
        db.commit.assert_called_once()


# ─── handle_order_fill task ───────────────────────────────────────────────────


class TestHandleOrderFill:
    """Tests for the handle_order_fill Celery task (_apply_fill async helper)."""

    @pytest.mark.asyncio
    async def test_buy_fill_opens_new_position(self) -> None:
        """A buy fill with no existing position creates a new long position."""
        from decimal import Decimal  # noqa: PLC0415
        from unittest.mock import AsyncMock, MagicMock  # noqa: PLC0415

        from app.tasks.fill_tasks import _apply_fill  # noqa: PLC0415

        import uuid  # noqa: PLC0415

        uid = uuid.uuid4()
        pid = uuid.uuid4()

        # Mock portfolio
        portfolio = MagicMock()
        portfolio.id = pid

        # No existing position
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[portfolio_result, position_result])
        session.add = MagicMock()  # sync method — not awaitable
        session.commit = AsyncMock()

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        from unittest.mock import patch  # noqa: PLC0415

        with patch("app.tasks.fill_tasks.AsyncSessionLocal", return_value=session_ctx):
            result = await _apply_fill("AAPL", "buy", 10.0, 150.0, str(uid))

        assert result["action"] == "opened"
        assert result["symbol"] == "AAPL"
        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_fill_closes_position_when_qty_reaches_zero(self) -> None:
        """A sell fill that exhausts quantity marks the position closed."""
        from decimal import Decimal  # noqa: PLC0415
        from unittest.mock import AsyncMock, MagicMock, patch  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from app.models.portfolio import Position  # noqa: PLC0415
        from app.tasks.fill_tasks import _apply_fill  # noqa: PLC0415

        uid = uuid.uuid4()
        pid = uuid.uuid4()

        portfolio = MagicMock()
        portfolio.id = pid

        position = Position(
            id=uuid.uuid4(),
            portfolio_id=pid,
            symbol="AAPL",
            asset_class="equity",
            side="long",
            quantity=Decimal("10"),
            avg_entry_price=Decimal("150.00"),
            is_open=True,
        )

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = position

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[portfolio_result, position_result])
        session.commit = AsyncMock()

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.fill_tasks.AsyncSessionLocal", return_value=session_ctx):
            result = await _apply_fill("AAPL", "sell", 10.0, 160.0, str(uid))

        assert result["action"] == "closed"
        assert position.is_open is False
        assert position.quantity == Decimal("0")

    @pytest.mark.asyncio
    async def test_buy_fill_averages_into_existing_position(self) -> None:
        """A buy fill into an existing position updates quantity and avg price."""
        from decimal import Decimal  # noqa: PLC0415
        from unittest.mock import AsyncMock, MagicMock, patch  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from app.models.portfolio import Position  # noqa: PLC0415
        from app.tasks.fill_tasks import _apply_fill  # noqa: PLC0415

        uid = uuid.uuid4()
        pid = uuid.uuid4()

        portfolio = MagicMock()
        portfolio.id = pid

        position = Position(
            id=uuid.uuid4(),
            portfolio_id=pid,
            symbol="MSFT",
            asset_class="equity",
            side="long",
            quantity=Decimal("5"),
            avg_entry_price=Decimal("400.00"),
            is_open=True,
        )

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        position_result = MagicMock()
        position_result.scalar_one_or_none.return_value = position

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[portfolio_result, position_result])
        session.commit = AsyncMock()

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.fill_tasks.AsyncSessionLocal", return_value=session_ctx):
            result = await _apply_fill("MSFT", "buy", 5.0, 420.0, str(uid))

        assert result["action"] == "updated"
        assert position.quantity == Decimal("10")
        # avg = (5*400 + 5*420) / 10 = 410
        from decimal import Decimal as D  # noqa: PLC0415
        assert position.avg_entry_price == D("410.0")

    @pytest.mark.asyncio
    async def test_skips_when_no_portfolio_found(self) -> None:
        """When the user has no portfolio, returns skipped without error."""
        from unittest.mock import AsyncMock, MagicMock, patch  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from app.tasks.fill_tasks import _apply_fill  # noqa: PLC0415

        uid = uuid.uuid4()

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=portfolio_result)

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.fill_tasks.AsyncSessionLocal", return_value=session_ctx):
            result = await _apply_fill("TSLA", "buy", 1.0, 200.0, str(uid))

        assert result["action"] == "skipped"
        assert result["symbol"] == "TSLA"
        session.commit.assert_not_called()
