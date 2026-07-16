"""
Python bridge to the QuantNexus C++ execution engine.

This module provides a pure-Python fallback when the compiled
``quantnexus_engine`` extension module is not available (e.g., in CI
environments where CMake/pybind11 are not installed).

When the C++ extension IS built (run ``scripts/build_engine.sh``),
this module re-exports everything from the compiled .so and is a thin
passthrough.

When the C++ extension is NOT available, this module provides Python
stub classes that emulate the interface — suitable for unit testing the
Python-side logic without requiring a C++ build environment.

Usage::

    from engine.python.engine_bridge import OrderBook, RiskManager, OrderManager

    book = OrderBook("EUR_USD")
    book.apply_snapshot(
        bids=[{"price": 1.085, "volume": 1e6}],
        asks=[{"price": 1.0851, "volume": 500e3}],
    )
    print(book.best_bid(), book.best_ask())

    risk = RiskManager()
    mgr  = OrderManager(risk)
    oid  = mgr.submit("AAPL", side="buy", quantity=100, limit_price=180.0)
    mgr.simulate_fill(oid, 180.0)
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any

# ── Try to load the compiled C++ extension first ──────────────────────────────
# Add the CMake build directory to the path if BUILD_DIR is set.
_BUILD_DIR = os.environ.get("ENGINE_BUILD_DIR", "")
if _BUILD_DIR and _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

_CPP_AVAILABLE = False
try:
    from quantnexus_engine import (  # type: ignore[import]
        OrderBook,
        OrderManager,
        RiskLimits,
        RiskManager,
        enable_kill_switch,
        disable_kill_switch,
        kill_switch_active,
    )
    _CPP_AVAILABLE = True
except ImportError:
    pass

# ── Python fallback stubs ─────────────────────────────────────────────────────
if not _CPP_AVAILABLE:

    _kill_switch_flag: bool = False

    def enable_kill_switch() -> None:
        global _kill_switch_flag
        _kill_switch_flag = True

    def disable_kill_switch() -> None:
        global _kill_switch_flag
        _kill_switch_flag = False

    def kill_switch_active() -> bool:
        return _kill_switch_flag

    class RiskLimits:
        def __init__(self) -> None:
            self.max_order_notional: float = 1_000_000.0
            self.max_position_size: float = 10_000.0
            self.max_daily_loss: float = -50_000.0
            self.concentration_limit: float = 0.25
            self.portfolio_nav: float = 1_000_000.0

    class RiskManager:
        def __init__(self, limits: RiskLimits | None = None) -> None:
            self._limits = limits or RiskLimits()
            self._positions: dict[str, float] = {}
            self._daily_pnl: float = 0.0
            self._allowed: set[str] = set()

        def check(self, symbol: str, side: int, quantity: float, price: float) -> tuple[bool, str]:
            notional = quantity * price
            if notional > self._limits.max_order_notional:
                return False, f"Notional {notional:.2f} exceeds limit"
            current = self._positions.get(symbol, 0.0)
            projected = current + side * quantity
            if abs(projected) > self._limits.max_position_size:
                return False, f"Position {projected:.0f} exceeds limit"
            if self._daily_pnl < self._limits.max_daily_loss:
                return False, f"Daily P&L {self._daily_pnl:.2f} below limit"
            if self._limits.portfolio_nav > 0:
                frac = notional / self._limits.portfolio_nav
                if frac > self._limits.concentration_limit:
                    return False, f"Concentration {frac*100:.1f}% exceeds limit"
            if self._allowed and symbol not in self._allowed:
                return False, f"Symbol {symbol} not in allow-list"
            return True, ""

        def record_fill(self, symbol: str, side: int, quantity: float, fill_price: float) -> None:
            self._positions[symbol] = self._positions.get(symbol, 0.0) + side * quantity

        def record_daily_pnl(self, delta: float) -> None:
            self._daily_pnl += delta

        def daily_pnl(self) -> float:
            return self._daily_pnl

        def positions(self) -> dict[str, float]:
            return dict(self._positions)

        def add_allowed_symbol(self, symbol: str) -> None:
            self._allowed.add(symbol)

        def clear_allowed_symbols(self) -> None:
            self._allowed.clear()

    class OrderBook:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol
            self._bids: dict[float, float] = {}
            self._asks: dict[float, float] = {}

        def apply_snapshot(
            self,
            bids: list[Any],
            asks: list[Any],
        ) -> None:
            self._bids = {}
            self._asks = {}
            for level in bids:
                p = level["price"] if isinstance(level, dict) else level.price
                v = level["volume"] if isinstance(level, dict) else level.volume
                if v > 0:
                    self._bids[p] = v
            for level in asks:
                p = level["price"] if isinstance(level, dict) else level.price
                v = level["volume"] if isinstance(level, dict) else level.volume
                if v > 0:
                    self._asks[p] = v

        def apply_update(self, is_bid: bool, price: float, volume: float) -> None:
            target = self._bids if is_bid else self._asks
            if volume <= 0:
                target.pop(price, None)
            else:
                target[price] = volume

        def best_bid(self) -> float | None:
            return max(self._bids) if self._bids else None

        def best_ask(self) -> float | None:
            return min(self._asks) if self._asks else None

        def mid_price(self) -> float | None:
            bb, ba = self.best_bid(), self.best_ask()
            return (bb + ba) / 2 if (bb is not None and ba is not None) else None

        def spread(self) -> float | None:
            bb, ba = self.best_bid(), self.best_ask()
            return (ba - bb) if (bb is not None and ba is not None) else None

        def level_count(self) -> int:
            return len(self._bids) + len(self._asks)

    class OrderManager:
        _kill_switch: bool = False

        def __init__(self, risk_manager: RiskManager) -> None:
            self._risk = risk_manager
            self._orders: dict[str, dict] = {}
            self._callbacks: list = []

        def submit(
            self,
            symbol: str,
            side: str = "buy",
            type: str = "market",
            quantity: float = 1.0,
            limit_price: float = 0.0,
            stop_price: float = 0.0,
        ) -> str:
            if kill_switch_active():
                raise RuntimeError("Order rejected: kill-switch is active")
            side_int = +1 if side == "buy" else -1
            ok, reason = self._risk.check(symbol, side_int, quantity, limit_price or stop_price or 1.0)
            if not ok:
                raise RuntimeError(f"Risk check failed: {reason}")
            oid = f"QN-{uuid.uuid4().hex[:12].upper()}"
            self._orders[oid] = {
                "client_order_id": oid,
                "symbol": symbol,
                "side": side,
                "type": type,
                "quantity": quantity,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "filled_qty": 0.0,
                "avg_fill_price": None,
                "status": "submitted",
            }
            return oid

        def cancel(self, client_order_id: str) -> bool:
            o = self._orders.get(client_order_id)
            if o is None or o["status"] in ("filled", "cancelled", "rejected"):
                return False
            o["status"] = "cancelled"
            return True

        def simulate_fill(self, client_order_id: str, fill_price: float) -> None:
            o = self._orders.get(client_order_id)
            if o is None:
                return
            o["filled_qty"] = o["quantity"]
            o["avg_fill_price"] = fill_price
            o["status"] = "filled"
            for cb in self._callbacks:
                cb(o)

        def on_fill(self, callback) -> None:  # type: ignore[no-untyped-def]
            self._callbacks.append(callback)

        def get_order(self, client_order_id: str) -> dict | None:
            return self._orders.get(client_order_id)

        def all_orders(self) -> list[dict]:
            return list(self._orders.values())

        @staticmethod
        def enable_kill_switch() -> None:
            enable_kill_switch()

        @staticmethod
        def disable_kill_switch() -> None:
            disable_kill_switch()

        @staticmethod
        def kill_switch_active() -> bool:
            return kill_switch_active()
