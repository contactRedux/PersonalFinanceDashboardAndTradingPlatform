"""
Unit tests — GET /market/vpvr/{symbol} endpoint (ST-I).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.jwt import create_access_token


def _auth_header() -> dict[str, str]:
    token = create_access_token({"sub": "u1", "email": "t@t.com", "role": "trader"})
    return {"Authorization": f"Bearer {token}"}


def _make_bar(close: float, volume: float) -> object:
    """Create a CanonicalBar instance with minimal required fields."""
    from app.data.ingestion.normalizer import CanonicalBar  # noqa: PLC0415

    return CanonicalBar(
        time=datetime.now(UTC),
        symbol="TEST",
        exchange="TEST",
        asset_class="equity",
        timeframe="1d",
        open=close - 1.0,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=volume,
    )


# ─── VPVR endpoint ────────────────────────────────────────────────────────────


class TestVPVREndpoint:
    """Tests for GET /api/v1/market/vpvr/{symbol}."""

    @pytest.mark.asyncio
    async def test_returns_expected_structure(self, client) -> None:
        """
        VPVR endpoint returns symbol, price_levels list, and poc field.
        Uses a mocked provider that returns synthetic bars.
        """
        fake_bars = [
            _make_bar(100.0, 1000.0),
            _make_bar(102.0, 2000.0),
            _make_bar(104.0, 1500.0),
            _make_bar(100.0, 3000.0),
            _make_bar(98.0, 800.0),
        ]

        mock_provider = MagicMock()
        mock_provider.get_bars = AsyncMock(return_value=fake_bars)

        with patch("app.api.v1.market.get_provider", return_value=mock_provider):
            resp = await client.get(
                "/api/v1/market/vpvr/AAPL",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert "price_levels" in body
        assert "poc" in body
        assert isinstance(body["price_levels"], list)
        assert len(body["price_levels"]) > 0

    @pytest.mark.asyncio
    async def test_price_levels_have_required_fields(self, client) -> None:
        """Each price level has price, volume, is_poc, pct_of_max fields."""
        fake_bars = [_make_bar(100.0 + i, 1000.0) for i in range(5)]

        mock_provider = MagicMock()
        mock_provider.get_bars = AsyncMock(return_value=fake_bars)

        with patch("app.api.v1.market.get_provider", return_value=mock_provider):
            resp = await client.get(
                "/api/v1/market/vpvr/MSFT",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        for level in body["price_levels"]:
            assert "price" in level
            assert "volume" in level
            assert "is_poc" in level
            assert "pct_of_max" in level
            assert isinstance(level["price"], float)
            assert isinstance(level["volume"], float)
            assert isinstance(level["is_poc"], bool)
            assert 0.0 <= level["pct_of_max"] <= 1.0

    @pytest.mark.asyncio
    async def test_exactly_one_poc_in_result(self, client) -> None:
        """Exactly one price level must have is_poc == True."""
        fake_bars = [
            _make_bar(100.0, 5000.0),
            _make_bar(100.0, 3000.0),
            _make_bar(105.0, 500.0),
            _make_bar(106.0, 200.0),
        ]

        mock_provider = MagicMock()
        mock_provider.get_bars = AsyncMock(return_value=fake_bars)

        with patch("app.api.v1.market.get_provider", return_value=mock_provider):
            resp = await client.get(
                "/api/v1/market/vpvr/TSLA?bins=4",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        poc_count = sum(1 for lvl in body["price_levels"] if lvl["is_poc"])
        assert poc_count == 1

    @pytest.mark.asyncio
    async def test_empty_result_when_no_bars(self, client) -> None:
        """When provider returns no bars, price_levels is empty and poc is None."""
        mock_provider = MagicMock()
        mock_provider.get_bars = AsyncMock(return_value=[])

        with patch("app.api.v1.market.get_provider", return_value=mock_provider):
            resp = await client.get(
                "/api/v1/market/vpvr/XYZ",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["price_levels"] == []
        assert body["poc"] is None

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client) -> None:
        """VPVR endpoint returns 401/403 without a valid JWT."""
        resp = await client.get("/api/v1/market/vpvr/AAPL")
        assert resp.status_code in (401, 403)


# ─── Tick data endpoint (ST-U) ────────────────────────────────────────────────


class TestTicksEndpoint:
    """Tests for GET /api/v1/market/ticks/{symbol}."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_unknown_symbol(self, client) -> None:
        """
        When the DB has no ticks for the given symbol, returns empty list (not 404).
        Uses a mocked DB session that returns no rows.
        """
        from unittest.mock import AsyncMock, MagicMock  # noqa: PLC0415
        from unittest.mock import patch  # noqa: PLC0415

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.dependencies.AsyncSessionLocal", return_value=mock_session):
            resp = await client.get(
                "/api/v1/market/ticks/UNKNOWNSYM",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "UNKNOWNSYM"
        assert body["ticks"] == []
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_returns_correct_structure_with_data(self, client) -> None:
        """
        When the DB returns tick rows, the response has the correct structure.
        """
        from unittest.mock import AsyncMock, MagicMock  # noqa: PLC0415
        from unittest.mock import patch  # noqa: PLC0415

        now = datetime.now(UTC)

        # Simulate DB row objects
        row1 = MagicMock()
        row1.time = now
        row1.price = 150.25
        row1.size = 100.0
        row1.side = "B"

        row2 = MagicMock()
        row2.time = now
        row2.price = 150.30
        row2.size = 50.0
        row2.side = "S"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row1, row2]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.dependencies.AsyncSessionLocal", return_value=mock_session):
            resp = await client.get(
                "/api/v1/market/ticks/AAPL",
                headers=_auth_header(),
                params={"limit": 100},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert isinstance(body["ticks"], list)
        assert body["count"] == len(body["ticks"])
        if body["ticks"]:
            tick = body["ticks"][0]
            assert "time" in tick
            assert "price" in tick
            assert "size" in tick
            assert "side" in tick


# ─── Snapshot enrichment (ST-AE) ─────────────────────────────────────────────

class TestSnapshotEnrichment:
    """Tests for GET /api/v1/market/snapshot/{symbol} — enriched response."""

    @pytest.mark.asyncio
    async def test_snapshot_returns_enriched_structure(self, client) -> None:
        """
        Snapshot endpoint returns quote + fundamentals dict + sentiment dict +
        latest_news list with all external calls mocked.
        """
        from app.data.ingestion.normalizer import CanonicalQuote  # noqa: PLC0415

        fake_quote = MagicMock()
        fake_quote.to_dict.return_value = {
            "symbol": "AAPL",
            "price": 195.0,
            "provider": "mock",
        }

        mock_provider = MagicMock()
        mock_provider.get_quote = AsyncMock(return_value=fake_quote)

        fake_fundamentals = {
            "trailingPE": 28.5,
            "marketCap": 3_000_000_000_000,
            "fiftyTwoWeekHigh": 220.0,
            "fiftyTwoWeekLow": 160.0,
        }

        mock_ticker = MagicMock()
        mock_ticker.info = fake_fundamentals

        with (
            patch("app.api.v1.market.get_provider", return_value=mock_provider),
            patch("app.api.v1.market.get_quotes", new_callable=AsyncMock, return_value={"AAPL": None}),
            patch("app.api.v1.market.set_quote", new_callable=AsyncMock),
            patch("app.api.v1.market.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
            patch(
                "app.services.news.aggregator.fetch_and_aggregate",
                new_callable=AsyncMock,
                return_value=[
                    {"headline": "Test news", "source": "newsapi", "published_at": "2025-01-01T00:00:00Z"}
                ],
            ),
        ):
            # to_thread is used for both yfinance and finbert; return info dict for yfinance
            mock_thread.return_value = fake_fundamentals

            resp = await client.get(
                "/api/v1/market/snapshot/AAPL",
                headers=_auth_header(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert "quote" in body
        assert "fundamentals" in body
        assert isinstance(body["fundamentals"], dict)
        assert "sentiment" in body
        assert isinstance(body["sentiment"], dict)
        assert "latest_news" in body
        assert isinstance(body["latest_news"], list)
        assert "timestamp" in body
