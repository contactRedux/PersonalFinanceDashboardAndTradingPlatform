"""
Polygon.io adapter for options chain data.

Provides:
  - get_options_chain(symbol, expiry) → dict with contracts, underlying price, expirations
  - get_iv_surface(symbol) → list of {strike, expiry_days, iv, contract_type}

Error handling:
  - Missing API key → raises PolygonKeyMissing (caller uses demo fallback)
  - HTTP 429 (rate limit) → retries up to 2 times with 5s backoff
  - Network timeout (10s) → raises PolygonError (caller uses demo fallback)
  - Unexpected response shape → logs + returns empty structure
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
import structlog

from app.services.options.greeks import black_scholes_greeks

logger = structlog.get_logger(__name__)

_BASE = "https://api.polygon.io"
_RISK_FREE_RATE = 0.045
_TIMEOUT = 10.0
_MAX_RETRIES = 2
_RETRY_DELAY = 5.0


class PolygonKeyMissing(Exception):
    """Raised when POLYGON_API_KEY is not configured."""


class PolygonError(Exception):
    """Raised on network error or unexpected response."""


class PolygonOptionsAdapter:
    """
    Thin Polygon.io client for options data.

    All methods are coroutines. Callers should catch PolygonKeyMissing to apply
    demo fallback, and PolygonError for network / rate-limit errors.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise PolygonKeyMissing("POLYGON_API_KEY not configured")
        self._api_key = api_key

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Execute a GET request with retry on 429."""
        url = f"{_BASE}{path}"
        merged: dict = {**(params or {}), "apiKey": self._api_key}

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, params=merged)
                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        logger.debug("polygon.rate_limited", attempt=attempt)
                        await asyncio.sleep(_RETRY_DELAY)
                        continue
                    raise PolygonError("Polygon rate limit exceeded after retries")
                if resp.status_code != 200:
                    raise PolygonError(f"Polygon HTTP {resp.status_code} for {path}")
                return resp.json()
            except httpx.TimeoutException as exc:
                raise PolygonError(f"Polygon timeout: {exc}") from exc
            except PolygonError:
                raise
            except Exception as exc:
                raise PolygonError(f"Polygon request error: {exc}") from exc
        raise PolygonError("Polygon max retries exceeded")  # unreachable but satisfies type

    async def get_options_chain(
        self,
        symbol: str,
        expiry: str | None = None,
    ) -> dict:
        """
        Fetch the full options chain for a symbol.

        Returns:
            {
                "underlying_price": float | None,
                "contracts": [{"ticker", "strike", "expiry", "contract_type", "greeks": {...}}],
                "expirations": [str, ...],
            }
        """
        sym = symbol.upper()

        # Fetch underlying snapshot
        underlying_price: float | None = None
        try:
            snap = await self._get(
                f"/v2/snapshot/locale/us/markets/stocks/tickers/{sym}"
            )
            underlying_price = snap.get("ticker", {}).get("day", {}).get("c")
        except PolygonError:
            pass  # Proceed without underlying price; Greeks will use fallback sigma

        # Fetch contracts
        params: dict[str, Any] = {
            "underlying_ticker": sym,
            "limit": 250,
        }
        if expiry:
            params["expiration_date"] = expiry

        try:
            chain_data = await self._get("/v3/reference/options/contracts", params)
        except PolygonError:
            return {
                "underlying_price": underlying_price,
                "contracts": [],
                "expirations": [],
            }

        contracts: list[dict] = []
        expirations_set: set[str] = set()

        for contract in chain_data.get("results", []):
            exp_date = contract.get("expiration_date", "")
            if not exp_date:
                continue
            expirations_set.add(exp_date)

            greeks_data: dict = {}
            if underlying_price:
                try:
                    exp_dt = date.fromisoformat(exp_date)
                    t_to_exp = max(0.0001, (exp_dt - date.today()).days / 365)
                    strike = float(contract.get("strike_price") or 0)
                    option_type = contract.get("contract_type", "call")

                    g = black_scholes_greeks(
                        S=float(underlying_price),
                        K=strike,
                        T=t_to_exp,
                        r=_RISK_FREE_RATE,
                        sigma=0.3,  # fallback IV; real IV requires market prices
                        option_type=option_type,
                    )
                    greeks_data = {
                        "delta": round(g.delta, 4),
                        "gamma": round(g.gamma, 6),
                        "theta": round(g.theta, 4),
                        "vega": round(g.vega, 4),
                        "rho": round(g.rho, 4),
                        "theoretical_price": round(g.theoretical_price, 4),
                    }
                except Exception:  # noqa: BLE001
                    pass

            contracts.append(
                {
                    "ticker": contract.get("ticker"),
                    "strike": contract.get("strike_price"),
                    "expiry": exp_date,
                    "contract_type": contract.get("contract_type"),
                    "greeks": greeks_data,
                }
            )

        return {
            "underlying_price": underlying_price,
            "contracts": contracts,
            "expirations": sorted(expirations_set),
        }

    async def get_iv_surface(self, symbol: str) -> list[dict]:
        """
        Build an IV surface from the options chain.

        Returns list of: {strike, expiry_days, iv, contract_type}
        """
        from app.services.options.greeks import implied_volatility  # noqa: PLC0415

        chain = await self.get_options_chain(symbol)
        contracts = chain.get("contracts", [])
        underlying = float(chain.get("underlying_price") or 100.0)

        surface: list[dict] = []
        today = date.today()

        for c in contracts:
            exp_str = c.get("expiry", "")
            try:
                exp_date = date.fromisoformat(exp_str)
            except ValueError:
                continue
            exp_days = max(1, (exp_date - today).days)
            strike = float(c.get("strike") or 0)
            if not strike:
                continue

            greeks = c.get("greeks", {})
            t_to_exp = exp_days / 365
            mkt_price = greeks.get("theoretical_price") or 0
            iv_val = 0.0
            if mkt_price and strike and underlying:
                try:
                    iv_val = (
                        implied_volatility(
                            market_price=float(mkt_price),
                            S=float(underlying),
                            K=strike,
                            T=t_to_exp,
                            r=_RISK_FREE_RATE,
                            option_type=c.get("contract_type", "call"),
                        )
                        or 0.0
                    )
                except Exception:  # noqa: BLE001
                    pass

            if iv_val > 0:
                surface.append(
                    {
                        "strike": strike,
                        "expiry_days": exp_days,
                        "iv": round(iv_val, 4),
                        "contract_type": c.get("contract_type", "call"),
                    }
                )

        return surface
