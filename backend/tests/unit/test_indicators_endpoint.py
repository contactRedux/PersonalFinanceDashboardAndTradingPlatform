"""
Unit tests — GET /market/indicators/{symbol} endpoint (ST-R).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from app.auth.jwt import create_access_token

_INDICATOR_KEYS = {"sma_20", "ema_50", "rsi_14", "macd_signal", "bb_upper", "bb_lower"}


def _auth_header() -> dict[str, str]:
    token = create_access_token({"sub": "u1", "email": "t@t.com", "role": "trader"})
    return {"Authorization": f"Bearer {token}"}


# ─── Response shape ────────────────────────────────────────────────────────────


class TestIndicatorsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_all_six_indicator_keys(self, client):
        """Endpoint must return all 6 indicator keys plus symbol and timestamp."""
        with patch("app.data.cache.redis_client.get_redis_pool", side_effect=Exception("no redis")):
            resp = await client.get(
                "/api/v1/market/indicators/AAPL",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert "timestamp" in body
        for key in _INDICATOR_KEYS:
            assert key in body, f"Missing indicator key: {key}"
            assert isinstance(body[key], float)

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/market/indicators/AAPL")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_symbol_is_uppercased(self, client):
        with patch("app.data.cache.redis_client.get_redis_pool", side_effect=Exception("no redis")):
            resp = await client.get(
                "/api/v1/market/indicators/aapl",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_bb_upper_greater_than_lower(self, client):
        with patch("app.data.cache.redis_client.get_redis_pool", side_effect=Exception("no redis")):
            resp = await client.get(
                "/api/v1/market/indicators/MSFT",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bb_upper"] > body["bb_lower"]

    @pytest.mark.asyncio
    async def test_rsi_in_valid_range(self, client):
        with patch("app.data.cache.redis_client.get_redis_pool", side_effect=Exception("no redis")):
            resp = await client.get(
                "/api/v1/market/indicators/TSLA",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        rsi = resp.json()["rsi_14"]
        assert 0.0 <= rsi <= 100.0


# ─── Redis caching path ────────────────────────────────────────────────────────


class TestIndicatorsCaching:
    @pytest.mark.asyncio
    async def test_cached_result_is_returned(self, client):
        """When Redis has a cached value it should be returned immediately."""
        cached_payload = {
            "symbol": "AAPL",
            "sma_20": 150.0,
            "ema_50": 148.5,
            "rsi_14": 55.0,
            "macd_signal": 1.2,
            "bb_upper": 160.0,
            "bb_lower": 140.0,
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_payload))

        with patch(
            "app.data.cache.redis_client.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            resp = await client.get(
                "/api/v1/market/indicators/AAPL",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sma_20"] == pytest.approx(150.0)
        assert body["bb_upper"] == pytest.approx(160.0)
        mock_redis.get.assert_called_once_with("indicators:AAPL")

    @pytest.mark.asyncio
    async def test_result_is_stored_in_redis_when_missing(self, client):
        """When cache miss, the computed result must be written back to Redis."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch(
            "app.data.cache.redis_client.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            resp = await client.get(
                "/api/v1/market/indicators/GOOG",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "indicators:GOOG"
        assert call_args[1].get("ex") == 300

    @pytest.mark.asyncio
    async def test_fallback_when_redis_unavailable(self, client):
        """When Redis raises on connect, endpoint still returns valid data."""
        with patch(
            "app.data.cache.redis_client.get_redis_pool",
            side_effect=Exception("connection refused"),
        ):
            resp = await client.get(
                "/api/v1/market/indicators/BTC-USD",
                headers=_auth_header(),
            )
        assert resp.status_code == 200
        body = resp.json()
        for key in _INDICATOR_KEYS:
            assert key in body


# ─── Indicator math helpers ────────────────────────────────────────────────────


class TestIndicatorHelpers:
    def test_sma_correct_value(self):
        from app.api.v1.market import _sma  # noqa: PLC0415

        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _sma(prices, 3) == pytest.approx(4.0)

    def test_rsi_all_gains_returns_100(self):
        from app.api.v1.market import _rsi  # noqa: PLC0415

        prices = list(range(1, 30))
        assert _rsi(prices, 14) == pytest.approx(100.0)

    def test_bollinger_upper_gt_lower(self):
        from app.api.v1.market import _bollinger  # noqa: PLC0415

        prices = [100.0 + i * 0.5 for i in range(30)]
        upper, lower = _bollinger(prices, 20)
        assert upper > lower

    def test_ema_single_element(self):
        from app.api.v1.market import _ema  # noqa: PLC0415

        assert _ema([42.0], 20) == pytest.approx(42.0)
