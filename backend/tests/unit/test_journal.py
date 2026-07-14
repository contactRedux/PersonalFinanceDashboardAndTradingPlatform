"""
Unit tests for ST-M: AI Trade Journal.

Tests:
  - analyze_trade task degrades gracefully when MongoDB is unavailable
  - GET /api/v1/journal returns {"entries": [], "count": 0} when MongoDB raises
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # noqa: F401

# ─── analyze_trade task — MongoDB unavailable ─────────────────────────────────


class TestAnalyzeTradeTask:
    """Tests for the analyze_trade Celery task internals (_analyze helper)."""

    @pytest.mark.asyncio
    async def test_logs_warning_and_returns_when_mongodb_unavailable(self) -> None:
        """
        When MongoDB is unavailable, _save_journal_entry logs a warning
        and does not raise; the overall _analyze call succeeds.
        """
        from app.models.order import Order  # noqa: PLC0415
        from app.tasks.journal_tasks import _analyze  # noqa: PLC0415

        order_id = str(uuid.uuid4())
        uid = uuid.uuid4()
        order = Order(
            id=uuid.UUID(order_id),
            user_id=uid,
            broker_order_id="broker-journal-1",
            client_order_id=None,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=10.0,
            status="filled",
            filled_qty=10.0,
            filled_avg_price=190.0,
            filled_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session)

        # motor.motor_asyncio.AsyncIOMotorClient raises when MongoDB unavailable
        motor_client_mock = MagicMock(side_effect=Exception("MongoDB not available"))

        _gen_mock = AsyncMock(return_value="Demo analysis.")
        with (
            patch("app.database.AsyncSessionLocal", mock_session_factory),
            patch("app.tasks.journal_tasks._read_sentiment", return_value=0.25),
            patch("app.tasks.journal_tasks._generate_analysis", new=_gen_mock),
            patch("motor.motor_asyncio.AsyncIOMotorClient", motor_client_mock),
        ):
            result = await _analyze(order_id)

        # Should complete without raising and return ok
        assert result["status"] == "ok"
        assert result["order_id"] == order_id

    @pytest.mark.asyncio
    async def test_returns_skipped_when_order_not_found(self) -> None:
        """When the order is not in the DB, task returns skipped."""
        from app.tasks.journal_tasks import _analyze  # noqa: PLC0415

        order_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session)

        with patch("app.database.AsyncSessionLocal", mock_session_factory):
            result = await _analyze(order_id)

        assert result["status"] == "skipped"
        assert result["reason"] == "order_not_found"

    @pytest.mark.asyncio
    async def test_saves_journal_entry_successfully(self) -> None:
        """When MongoDB is available, insert_one is called with the correct shape."""
        from app.models.order import Order  # noqa: PLC0415
        from app.tasks.journal_tasks import _analyze  # noqa: PLC0415

        order_id = str(uuid.uuid4())
        uid = uuid.uuid4()
        order = Order(
            id=uuid.UUID(order_id),
            user_id=uid,
            broker_order_id="broker-journal-2",
            client_order_id=None,
            symbol="NVDA",
            side="sell",
            order_type="market",
            quantity=5.0,
            status="filled",
            filled_qty=5.0,
            filled_avg_price=500.0,
            filled_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session)

        # Mock motor client + collection
        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.trade_journal = mock_collection
        mock_motor_client = MagicMock()
        mock_motor_client.__getitem__ = MagicMock(return_value=mock_db)

        inserted_docs: list[dict] = []

        async def fake_insert(doc: dict) -> None:
            inserted_docs.append(doc)

        mock_collection.insert_one = fake_insert

        _gen_mock2 = AsyncMock(return_value="Test analysis.")
        with (
            patch("app.database.AsyncSessionLocal", mock_session_factory),
            patch("app.tasks.journal_tasks._read_sentiment", return_value=0.1),
            patch("app.tasks.journal_tasks._generate_analysis", new=_gen_mock2),
            patch("motor.motor_asyncio.AsyncIOMotorClient", return_value=mock_motor_client),
        ):
            result = await _analyze(order_id)

        assert result["status"] == "ok"
        assert len(inserted_docs) == 1
        doc = inserted_docs[0]
        assert doc["symbol"] == "NVDA"
        assert doc["side"] == "sell"
        assert doc["user_id"] == str(uid)
        assert doc["ai_analysis"] == "Test analysis."


# ─── GET /api/v1/journal — MongoDB unavailable ────────────────────────────────


class TestJournalEndpoint:
    @pytest.mark.asyncio
    async def test_returns_empty_when_mongodb_raises(self) -> None:
        """GET /journal returns {"entries": [], "count": 0} when MongoDB raises."""
        from app.api.v1.journal import get_journal  # noqa: PLC0415

        current_user = {"sub": str(uuid.uuid4())}

        with patch(
            "motor.motor_asyncio.AsyncIOMotorClient",
            side_effect=Exception("MongoDB not available"),
        ):
            response = await get_journal(current_user=current_user)

        assert response == {"entries": [], "count": 0}

    @pytest.mark.asyncio
    async def test_returns_entries_when_mongodb_available(self) -> None:
        """GET /journal returns entries fetched from MongoDB."""
        from app.api.v1.journal import get_journal  # noqa: PLC0415

        user_id = str(uuid.uuid4())
        current_user = {"sub": user_id}

        sample_entries = [
            {
                "order_id": str(uuid.uuid4()),
                "user_id": user_id,
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 10.0,
                "entry_price": 190.0,
                "sentiment_score": 0.3,
                "technical_context": {"rsi": 54.2},
                "ai_analysis": "Bullish setup.",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]

        # Build an async iterable cursor mock
        async def _aiter(_self):  # noqa: ANN001, ANN202
            for e in sample_entries:
                yield {**e}

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = _aiter
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)

        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.trade_journal = mock_collection

        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("motor.motor_asyncio.AsyncIOMotorClient", return_value=mock_client):
            response = await get_journal(current_user=current_user)

        assert response["count"] == 1
        assert response["entries"][0]["symbol"] == "AAPL"
