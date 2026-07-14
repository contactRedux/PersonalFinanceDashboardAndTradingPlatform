# Developer Guide: Adding Market Data Providers

This guide walks through the steps to register a new external market data provider in
QuantNexus — from implementing the abstract interface through to Docker configuration and tests.

---

## Overview

All market data providers implement the [`MarketDataProvider`](../../backend/app/services/market_data/base.py)
abstract base class. The provider router (`router.py`) selects the active provider at runtime
based on the `MARKET_DATA_PROVIDER` environment variable. Adding a new provider requires:

1. Implementing the base class
2. Registering in the router factory
3. Adding the API key env var to `config.py`
4. Documenting in `.env.example`
5. Writing unit tests
6. Updating `docker-compose.yml`

---

## Step 1 — Implement the base class

**Reference:** [`backend/app/services/market_data/base.py`](../../backend/app/services/market_data/base.py)

Create a new file: `backend/app/services/market_data/myprovider.py`

```python
"""MyProvider market data adapter."""

from __future__ import annotations

import httpx
import structlog
from collections.abc import AsyncGenerator

from app.data.ingestion.normalizer import CanonicalBar, CanonicalQuote
from app.services.market_data.base import MarketDataProvider

logger = structlog.get_logger(__name__)


class MyProvider(MarketDataProvider):
    name = "myprovider"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError(
                "MyProvider requires MYPROVIDER_API_KEY to be set. "
                "Get a key at https://myprovider.example.com/account."
            )
        self._api_key = api_key
        self._base_url = "https://api.myprovider.example.com/v1"

    async def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 500,
    ) -> list[CanonicalBar]:
        params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{self._base_url}/bars",
                        params=params,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                    )
                if response.status_code == 429:
                    # Exponential backoff on rate limit
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                raw = response.json()
                return [
                    CanonicalBar(
                        time=item["t"],
                        open=float(item["o"]),
                        high=float(item["h"]),
                        low=float(item["l"]),
                        close=float(item["c"]),
                        volume=float(item["v"]),
                    )
                    for item in raw.get("bars", [])
                ]
            except httpx.TimeoutException as exc:
                logger.warning("myprovider.get_bars.timeout", attempt=attempt, symbol=symbol)
                if attempt == 2:
                    raise
        return []

    async def get_quote(self, symbol: str) -> CanonicalQuote | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self._base_url}/quote/{symbol}",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            response.raise_for_status()
            data = response.json()
            return CanonicalQuote(
                symbol=symbol,
                price=float(data["price"]),
                timestamp=data["timestamp"],
            )
        except Exception:
            logger.exception("myprovider.get_quote.error", symbol=symbol)
            return None

    async def get_quotes(self, symbols: list[str]) -> dict[str, CanonicalQuote | None]:
        # Implement batch quotes; fall back to individual calls if no batch endpoint
        results = {}
        for symbol in symbols:
            results[symbol] = await self.get_quote(symbol)
        return results

    async def stream_quotes(self, symbols: list[str]) -> AsyncGenerator[CanonicalQuote, None]:
        # Implement WebSocket streaming or long-poll; raise NotImplementedError if unsupported
        raise NotImplementedError("MyProvider does not support streaming quotes")
        yield  # type: ignore[misc]
```

### Error handling rules

| Scenario | Required behaviour |
|----------|--------------------|
| API key absent (`""`) | Raise `ValueError` with a clear message including where to get a key |
| Request timeout | Catch `httpx.TimeoutException`, retry up to 3 times, re-raise on third failure |
| HTTP 429 rate limit | Retry with exponential backoff: 1s, 2s, 4s before failing |
| HTTP 4xx/5xx from provider | Log the error, return `None` (quotes) or `[]` (bars); do not crash the API |

---

## Step 2 — Register in the provider router

**File:** [`backend/app/services/market_data/router.py`](../../backend/app/services/market_data/router.py)

Locate the factory function (`get_provider`) and add a new entry:

```python
from app.services.market_data.myprovider import MyProvider

def get_provider() -> MarketDataProvider:
    name = settings.market_data_provider.lower()
    if name == "alpaca":
        return AlpacaProvider(api_key=settings.alpaca_api_key, ...)
    elif name == "myprovider":                          # ← add this block
        return MyProvider(api_key=settings.myprovider_api_key)
    else:
        return YahooFinanceProvider()
```

---

## Step 3 — Add the env var to config

**File:** [`backend/app/config.py`](../../backend/app/config.py)

Add the new API key field to the `Settings` class, grouped with the other provider keys:

```python
# ─── Market Data Providers ────────────────────────────────────────────────────
myprovider_api_key: str = ""
```

An empty string default ensures the application starts without the key set; the `ValueError`
in the provider constructor fires only when the provider is actually selected.

---

## Step 4 — Document in `.env.example`

Add the new variable with a comment explaining what it does and where to obtain a key:

```bash
# MyProvider market data API key.
# Required when MARKET_DATA_PROVIDER=myprovider.
# Sign up and generate a key at: https://myprovider.example.com/account/api-keys
MYPROVIDER_API_KEY=
```

---

## Step 5 — Write unit tests

**Pattern:** [`backend/tests/unit/test_adapters.py`](../../backend/tests/unit/test_adapters.py)

Write at least three test cases:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.services.market_data.myprovider import MyProvider


def test_myprovider_raises_on_missing_key():
    """Provider must raise ValueError when api_key is empty."""
    with pytest.raises(ValueError, match="MYPROVIDER_API_KEY"):
        MyProvider(api_key="")


@pytest.mark.asyncio
async def test_myprovider_get_bars_happy_path():
    """Provider returns CanonicalBar list on a successful response."""
    mock_response = {
        "bars": [
            {"t": "2024-01-02T00:00:00Z", "o": 185.0, "h": 187.0,
             "l": 184.5, "c": 186.0, "v": 50_000_000},
        ]
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = lambda: None

        provider = MyProvider(api_key="test-key")
        bars = await provider.get_bars("AAPL", "1d", limit=1)

    assert len(bars) == 1
    assert bars[0].close == 186.0


@pytest.mark.asyncio
async def test_myprovider_get_bars_timeout_raises():
    """Provider re-raises TimeoutException after 3 retries."""
    import httpx

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
        provider = MyProvider(api_key="test-key")
        with pytest.raises(httpx.TimeoutException):
            await provider.get_bars("AAPL", "1d")
```

---

## Step 6 — Update docker-compose.yml

Add the new env var name to the `backend.environment` section (and optionally to
`celery_worker.environment` if the worker also calls the provider). Set it to an empty string as
the default so the compose file can be committed without real credentials:

```yaml
services:
  backend:
    environment:
      - MYPROVIDER_API_KEY=${MYPROVIDER_API_KEY:-}
  celery_worker:
    environment:
      - MYPROVIDER_API_KEY=${MYPROVIDER_API_KEY:-}
```

The `${VAR:-}` syntax means: use the host environment variable if set, otherwise default to
empty string. The real key is injected at deployment time via CI secrets or a `.env` file that
is not committed to version control.

---

## Checklist

- [ ] New file `backend/app/services/market_data/myprovider.py` implementing `MarketDataProvider`
- [ ] `ValueError` raised when API key is absent
- [ ] Timeout handled with retry + exponential backoff
- [ ] HTTP 429 handled with exponential backoff
- [ ] Registered in `backend/app/services/market_data/router.py` factory
- [ ] `myprovider_api_key: str = ""` added to `backend/app/config.py`
- [ ] `MYPROVIDER_API_KEY=` added to `.env.example` with explanation comment
- [ ] Unit tests written: missing key, happy path, timeout — all passing
- [ ] `docker-compose.yml` `backend.environment` updated
- [ ] `uv run pytest tests/unit/ -v` passes with zero failures
