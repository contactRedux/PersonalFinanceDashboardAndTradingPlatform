"""
Order Management Service — Alpaca paper trading integration.

Responsibilities:
  - Place market / limit / stop orders via Alpaca paper trading REST API
  - Cancel open orders
  - Poll and sync order status
  - Persist orders to PostgreSQL

Paper trading base URL: https://paper-api.alpaca.markets
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_PAPER_BASE = "https://paper-api.alpaca.markets"


def _alpaca_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key or "",
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret or settings.alpaca_secret_key or "",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _is_alpaca_available() -> bool:
    secret = settings.alpaca_api_secret or settings.alpaca_secret_key
    return bool(settings.alpaca_api_key and secret)


# ─── Order schemas (internal, no SQLAlchemy) ──────────────────────────────────


class OrderRequest:
    """Validated order request ready for submission."""

    def __init__(
        self,
        user_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "day",
        order_class: str = "simple",
        take_profit_price: float | None = None,
        stop_loss_price: float | None = None,
    ) -> None:
        if order_type in ("limit", "stop_limit") and limit_price is None:
            raise ValueError("limit_price required for limit/stop_limit orders")
        if order_class == "bracket":
            if take_profit_price is None or stop_loss_price is None:
                msg = "take_profit_price and stop_loss_price required for bracket orders"
                raise ValueError(msg)

        self.user_id = user_id
        self.symbol = symbol.upper()
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.order_class = order_class
        self.take_profit_price = take_profit_price
        self.stop_loss_price = stop_loss_price
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("market", "limit", "stop", "stop_limit"):
            raise ValueError(f"Invalid order_type: {order_type}")
        if order_class not in ("simple", "bracket", "oco"):
            raise ValueError(f"Invalid order_class: {order_class}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        self.client_order_id = str(uuid.uuid4())


class OrderResult:
    """Normalised order result from the broker."""

    def __init__(
        self,
        order_id: str,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        status: str,
        filled_qty: float = 0.0,
        filled_avg_price: float | None = None,
        submitted_at: datetime | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
        raw: dict | None = None,
    ) -> None:
        self.order_id = order_id
        self.client_order_id = client_order_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.status = status
        self.filled_qty = filled_qty
        self.filled_avg_price = filled_avg_price
        self.submitted_at = submitted_at or datetime.now(UTC)
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.raw = raw or {}


def _parse_alpaca_order(data: dict) -> OrderResult:
    """Parse Alpaca order response into OrderResult."""
    return OrderResult(
        order_id=data["id"],
        client_order_id=data.get("client_order_id", ""),
        symbol=data["symbol"],
        side=data["side"],
        order_type=data["order_type"],
        quantity=float(data.get("qty") or data.get("notional") or 0),
        status=data["status"],
        filled_qty=float(data.get("filled_qty") or 0),
        filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
        submitted_at=datetime.fromisoformat(data["submitted_at"].replace("Z", "+00:00"))
        if data.get("submitted_at")
        else None,
        limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
        stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
        raw=data,
    )


# ─── Service functions ────────────────────────────────────────────────────────


async def place_order(req: OrderRequest) -> OrderResult:
    """
    Submit an order to Alpaca paper trading.

    Falls back to a simulated fill if Alpaca is not configured.
    """
    if not _is_alpaca_available():
        # Simulate an immediate fill for development without API keys
        logger.warning("orders.alpaca_unavailable.simulating_fill", symbol=req.symbol)
        return OrderResult(
            order_id=str(uuid.uuid4()),
            client_order_id=req.client_order_id,
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            status="filled",
            filled_qty=req.quantity,
            filled_avg_price=req.limit_price or 100.0,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )

    payload: dict = {
        "symbol": req.symbol,
        "qty": str(req.quantity),
        "side": req.side,
        "type": req.order_type,
        "time_in_force": req.time_in_force,
        "client_order_id": req.client_order_id,
    }
    if req.limit_price is not None:
        payload["limit_price"] = str(req.limit_price)
    if req.stop_price is not None:
        payload["stop_price"] = str(req.stop_price)
    if req.order_class == "bracket":
        payload["order_class"] = "bracket"
        payload["take_profit"] = {"limit_price": str(req.take_profit_price)}
        payload["stop_loss"] = {"stop_price": str(req.stop_loss_price)}
    elif req.order_class == "oco":
        payload["order_class"] = "oco"
        payload["take_profit"] = {"limit_price": str(req.take_profit_price)}
        payload["stop_loss"] = {"stop_price": str(req.stop_loss_price)}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{_PAPER_BASE}/v2/orders",
            json=payload,
            headers=_alpaca_headers(),
        )
        resp.raise_for_status()
        return _parse_alpaca_order(resp.json())


async def cancel_order(broker_order_id: str) -> bool:
    """Cancel an open order. Returns True on success."""
    if not _is_alpaca_available():
        logger.warning("orders.alpaca_unavailable.simulating_cancel")
        return True

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{_PAPER_BASE}/v2/orders/{broker_order_id}",
            headers=_alpaca_headers(),
        )
        return resp.status_code in (200, 204)


async def get_open_orders(symbol: str | None = None) -> list[OrderResult]:
    """Fetch all open orders (optionally filtered by symbol)."""
    if not _is_alpaca_available():
        return []

    params: dict = {"status": "open"}
    if symbol:
        params["symbols"] = symbol.upper()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_PAPER_BASE}/v2/orders",
            params=params,
            headers=_alpaca_headers(),
        )
        resp.raise_for_status()
        return [_parse_alpaca_order(o) for o in resp.json()]


async def modify_order(
    broker_order_id: str,
    qty: float | None = None,
    limit_price: float | None = None,
) -> OrderResult | None:
    """
    Modify an open order (qty and/or limit_price).

    Returns the updated OrderResult, or None when Alpaca is unavailable
    (in demo mode, returns a simulated updated result).
    """
    if not _is_alpaca_available():
        logger.warning("orders.alpaca_unavailable.simulating_modify")
        return OrderResult(
            order_id=broker_order_id,
            client_order_id="",
            symbol="",
            side="buy",
            order_type="limit",
            quantity=qty or 0.0,
            status="pending_replace",
            limit_price=limit_price,
        )

    patch: dict = {}
    if qty is not None:
        patch["qty"] = str(qty)
    if limit_price is not None:
        patch["limit_price"] = str(limit_price)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{_PAPER_BASE}/v2/orders/{broker_order_id}",
            json=patch,
            headers=_alpaca_headers(),
        )
        resp.raise_for_status()
        return _parse_alpaca_order(resp.json())


async def get_order_by_id(broker_order_id: str) -> OrderResult | None:
    """Fetch a specific order by its broker order ID."""
    if not _is_alpaca_available():
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{_PAPER_BASE}/v2/orders/{broker_order_id}",
            headers=_alpaca_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _parse_alpaca_order(resp.json())
