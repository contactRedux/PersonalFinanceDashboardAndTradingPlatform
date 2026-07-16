"""
OANDA Forex Order Service.

Submits, cancels, and tracks forex orders via the OANDA v20 REST API.
Uses paper (practice) by default; switches to live when OANDA_BASE_URL is
set to https://api-fxtrade.oanda.com.

Only active when both OANDA_API_KEY and OANDA_ACCOUNT_ID are configured.
Falls back to simulated fill in development mode when credentials are absent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _is_available() -> bool:
    return bool(settings.oanda_api_key and settings.oanda_account_id)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.oanda_api_key}",
        "Content-Type": "application/json",
        "Accept-Datetime-Format": "RFC3339",
    }


def _base() -> str:
    return settings.oanda_base_url.rstrip("/")


def _normalise_symbol(symbol: str) -> str:
    """Convert EUR/USD or EURUSD → EUR_USD (OANDA instrument format)."""
    sym = symbol.upper()
    if "/" in sym:
        return sym.replace("/", "_")
    if "_" not in sym and len(sym) == 6:
        return f"{sym[:3]}_{sym[3:]}"
    return sym


# ─── Order schemas ────────────────────────────────────────────────────────────


class OANDAOrderRequest:
    """Validated forex order request."""

    def __init__(
        self,
        user_id: str,
        symbol: str,
        side: str,
        order_type: str,
        units: float,
        price: float | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        time_in_force: str = "GTC",
    ) -> None:
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("market", "limit", "stop"):
            raise ValueError(f"Invalid order_type: {order_type}")
        if order_type in ("limit", "stop") and price is None:
            raise ValueError(f"price is required for {order_type} orders")
        if units <= 0:
            raise ValueError("units must be positive")

        self.user_id = user_id
        self.instrument = _normalise_symbol(symbol)
        self.side = side
        self.order_type = order_type
        # OANDA uses signed units: positive = buy, negative = sell
        self.units = units if side == "buy" else -units
        self.price = price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.time_in_force = time_in_force
        self.client_order_id = str(uuid.uuid4())


class OANDAOrderResult:
    """Normalised order result from OANDA."""

    def __init__(
        self,
        order_id: str,
        client_order_id: str,
        instrument: str,
        side: str,
        order_type: str,
        units: float,
        status: str,
        fill_price: float | None = None,
        filled_at: datetime | None = None,
        raw: dict | None = None,
    ) -> None:
        self.order_id = order_id
        self.client_order_id = client_order_id
        self.instrument = instrument
        self.side = side
        self.order_type = order_type
        self.units = abs(units)
        self.status = status
        self.fill_price = fill_price
        self.filled_at = filled_at
        self.raw = raw or {}


def _parse_response(data: dict) -> OANDAOrderResult:
    """
    Parse OANDA POST /v3/accounts/{id}/orders response.

    OANDA returns either orderFillTransaction (immediate fill) or
    orderCreateTransaction (pending order), depending on order type.
    """
    fill_tx: dict[str, Any] = data.get("orderFillTransaction", {})
    create_tx: dict[str, Any] = data.get("orderCreateTransaction", {})
    related = data.get("relatedTransactionIDs", [])

    if fill_tx:
        # Market order filled immediately
        order_id = str(fill_tx.get("id", uuid.uuid4()))
        instrument = fill_tx.get("instrument", "")
        units = float(fill_tx.get("units", 0))
        price_raw = fill_tx.get("price") or fill_tx.get("tradeOpened", {}).get("price")
        fill_price = float(price_raw) if price_raw else None
        ts_raw = fill_tx.get("time", "")
        try:
            filled_at = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            filled_at = datetime.now(UTC)
        status = "filled"
    else:
        order_id = str(related[0]) if related else str(uuid.uuid4())
        order_detail = data.get("orderCreateTransaction", {})
        instrument = order_detail.get("instrument", "")
        units = float(order_detail.get("units", 0))
        fill_price = None
        filled_at = None
        status = "submitted"

    side = "buy" if units >= 0 else "sell"
    order_type = create_tx.get("type", "MARKET_ORDER").replace("_ORDER", "").lower()

    return OANDAOrderResult(
        order_id=order_id,
        client_order_id=create_tx.get("requestID", str(uuid.uuid4())),
        instrument=instrument,
        side=side,
        order_type=order_type,
        units=units,
        status=status,
        fill_price=fill_price,
        filled_at=filled_at,
        raw=data,
    )


# ─── Service functions ────────────────────────────────────────────────────────


async def place_forex_order(req: OANDAOrderRequest) -> OANDAOrderResult:
    """
    Submit a forex order to OANDA.

    Falls back to simulated fill when OANDA credentials are not configured.
    """
    if not _is_available():
        logger.warning("oanda_orders.unavailable.simulating_fill", instrument=req.instrument)
        sim_price = req.price or 1.1000
        return OANDAOrderResult(
            order_id=str(uuid.uuid4()),
            client_order_id=req.client_order_id,
            instrument=req.instrument,
            side=req.side,
            order_type=req.order_type,
            units=abs(req.units),
            status="filled",
            fill_price=sim_price,
            filled_at=datetime.now(UTC),
        )

    order_body: dict[str, Any] = {
        "units": str(req.units),
        "instrument": req.instrument,
        "timeInForce": req.time_in_force,
    }

    if req.order_type == "market":
        order_body["type"] = "MARKET"
    elif req.order_type == "limit":
        order_body["type"] = "LIMIT"
        order_body["price"] = str(req.price)
    elif req.order_type == "stop":
        order_body["type"] = "STOP"
        order_body["price"] = str(req.price)

    if req.stop_loss_price is not None:
        order_body["stopLossOnFill"] = {"price": str(req.stop_loss_price)}
    if req.take_profit_price is not None:
        order_body["takeProfitOnFill"] = {"price": str(req.take_profit_price)}

    url = f"{_base()}/v3/accounts/{settings.oanda_account_id}/orders"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json={"order": order_body}, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    result = _parse_response(data)
    logger.info(
        "oanda_orders.placed",
        user_id=req.user_id,
        instrument=req.instrument,
        side=req.side,
        units=abs(req.units),
        status=result.status,
    )
    return result


async def cancel_forex_order(order_id: str) -> bool:
    """
    Cancel a pending OANDA order.

    Returns True on success (204 or 200); False on any failure.
    """
    if not _is_available():
        logger.warning("oanda_orders.unavailable.simulating_cancel")
        return True

    url = f"{_base()}/v3/accounts/{settings.oanda_account_id}/orders/{order_id}/cancel"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.put(url, headers=_headers())
        return resp.status_code in (200, 201)


async def get_open_forex_orders(instrument: str | None = None) -> list[OANDAOrderResult]:
    """
    Fetch pending OANDA orders, optionally filtered by instrument.
    """
    if not _is_available():
        return []

    url = f"{_base()}/v3/accounts/{settings.oanda_account_id}/orders"
    params: dict = {"state": "PENDING"}
    if instrument:
        params["instrument"] = _normalise_symbol(instrument)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    results: list[OANDAOrderResult] = []
    for o in data.get("orders", []):
        units = float(o.get("units", 0))
        side = "buy" if units >= 0 else "sell"
        results.append(
            OANDAOrderResult(
                order_id=str(o.get("id", "")),
                client_order_id=str(o.get("clientExtensions", {}).get("id", "")),
                instrument=o.get("instrument", ""),
                side=side,
                order_type=o.get("type", "LIMIT").replace("_ORDER", "").lower(),
                units=units,
                status="pending",
                raw=o,
            )
        )
    return results
