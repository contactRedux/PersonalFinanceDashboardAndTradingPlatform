"""
Tests for the C++ engine Python bridge fallback stubs (Track F).

These tests run against engine/python/engine_bridge.py which provides
pure-Python fallback implementations of OrderBook, RiskManager, and
OrderManager.  When the compiled C++ extension is available, the bridge
transparently delegates to it and these tests validate the interface contract.
"""

from __future__ import annotations

import os
import sys

import pytest

# Make engine/python importable
# __file__ is at:  <repo>/backend/tests/unit/test_track_f_engine.py
# engine/python is at: <repo>/engine/python/
# So we go up 4 levels to reach <repo>, then descend into engine/python.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO_ROOT = os.path.dirname(_BACKEND_ROOT)
_ENGINE_PYTHON = os.path.join(_REPO_ROOT, "engine", "python")
if _ENGINE_PYTHON not in sys.path:
    sys.path.insert(0, _ENGINE_PYTHON)


# ────────────────────────────────────────────────────────────────────────────
# F-2 · OrderBook
# ────────────────────────────────────────────────────────────────────────────


class TestOrderBook:
    def test_empty_book_has_no_best_bid_or_ask(self):
        from engine_bridge import OrderBook

        book = OrderBook("EUR_USD")
        assert book.best_bid() is None
        assert book.best_ask() is None
        assert book.mid_price() is None
        assert book.spread() is None

    def test_apply_snapshot_sets_best_bid_ask(self):
        from engine_bridge import OrderBook

        book = OrderBook("AAPL")
        book.apply_snapshot(
            bids=[{"price": 180.0, "volume": 100}, {"price": 179.9, "volume": 200}],
            asks=[{"price": 180.1, "volume": 50}, {"price": 180.2, "volume": 150}],
        )
        assert book.best_bid() == pytest.approx(180.0)
        assert book.best_ask() == pytest.approx(180.1)

    def test_mid_price_and_spread(self):
        from engine_bridge import OrderBook

        book = OrderBook("SPY")
        book.apply_snapshot(
            bids=[{"price": 500.0, "volume": 1000}],
            asks=[{"price": 500.1, "volume": 1000}],
        )
        assert book.mid_price() == pytest.approx(500.05)
        assert book.spread() == pytest.approx(0.1)

    def test_apply_update_adds_level(self):
        from engine_bridge import OrderBook

        book = OrderBook("BTC_USD")
        book.apply_update(True, 50000.0, 0.5)
        assert book.best_bid() == pytest.approx(50000.0)

    def test_apply_update_removes_level_when_zero_volume(self):
        from engine_bridge import OrderBook

        book = OrderBook("TSLA")
        book.apply_snapshot(
            bids=[{"price": 250.0, "volume": 100}],
            asks=[{"price": 251.0, "volume": 100}],
        )
        book.apply_update(True, 250.0, 0.0)
        assert book.best_bid() is None

    def test_level_count(self):
        from engine_bridge import OrderBook

        book = OrderBook("NVDA")
        assert book.level_count() == 0
        book.apply_snapshot(
            bids=[{"price": 900.0, "volume": 1}],
            asks=[{"price": 900.1, "volume": 1}, {"price": 900.2, "volume": 1}],
        )
        assert book.level_count() == 3


# ────────────────────────────────────────────────────────────────────────────
# F-1 · RiskManager
# ────────────────────────────────────────────────────────────────────────────


class TestRiskManager:
    def _make_risk(self):
        from engine_bridge import RiskLimits, RiskManager

        limits = RiskLimits()
        limits.max_order_notional = 100_000.0
        limits.max_position_size = 1_000.0
        limits.max_daily_loss = -10_000.0
        limits.concentration_limit = 0.25
        limits.portfolio_nav = 1_000_000.0
        return RiskManager(limits)

    def test_valid_order_is_approved(self):
        rm = self._make_risk()
        ok, reason = rm.check("AAPL", +1, 100, 180.0)
        assert ok is True
        assert reason == ""

    def test_excessive_notional_rejected(self):
        rm = self._make_risk()
        ok, reason = rm.check("TSLA", +1, 1000, 200.0)
        assert ok is False
        assert reason != ""

    def test_daily_loss_limit_rejection(self):
        rm = self._make_risk()
        rm.record_daily_pnl(-15_000.0)
        ok, reason = rm.check("SPY", +1, 1, 500.0)
        assert ok is False

    def test_allow_list_blocks_unlisted_symbol(self):
        rm = self._make_risk()
        rm.add_allowed_symbol("AAPL")
        ok_apple, _ = rm.check("AAPL", +1, 10, 180.0)
        ok_tsla, _ = rm.check("TSLA", +1, 10, 200.0)
        assert ok_apple is True
        assert ok_tsla is False

    def test_position_accumulates(self):
        rm = self._make_risk()
        rm.record_fill("AAPL", +1, 100, 180.0)
        rm.record_fill("AAPL", -1, 30, 182.0)
        pos = rm.positions()
        assert pos["AAPL"] == pytest.approx(70.0)

    def test_daily_pnl_accumulates(self):
        rm = self._make_risk()
        rm.record_daily_pnl(-1000.0)
        rm.record_daily_pnl(400.0)
        assert rm.daily_pnl() == pytest.approx(-600.0)


# ────────────────────────────────────────────────────────────────────────────
# F-1 · OrderManager
# ────────────────────────────────────────────────────────────────────────────


class TestOrderManager:
    def _make_mgr(self):
        from engine_bridge import OrderManager, RiskLimits, RiskManager, disable_kill_switch

        disable_kill_switch()
        limits = RiskLimits()
        limits.max_order_notional = 1_000_000.0
        limits.max_position_size = 100_000.0
        limits.max_daily_loss = -1_000_000.0
        limits.portfolio_nav = 100_000_000.0
        risk = RiskManager(limits)
        return OrderManager(risk)

    def test_submit_returns_non_empty_id(self):
        mgr = self._make_mgr()
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        assert oid and len(oid) > 0

    def test_submitted_order_has_status_submitted(self):
        mgr = self._make_mgr()
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        order = mgr.get_order(oid)
        assert order is not None
        assert order["status"] == "submitted"

    def test_simulate_fill_updates_status(self):
        mgr = self._make_mgr()
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        mgr.simulate_fill(oid, 180.0)
        order = mgr.get_order(oid)
        assert order["status"] == "filled"
        assert order["avg_fill_price"] == pytest.approx(180.0)

    def test_fill_callback_fires(self):
        mgr = self._make_mgr()
        fired = []
        mgr.on_fill(lambda o: fired.append(o["status"]))
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        mgr.simulate_fill(oid, 180.0)
        assert "filled" in fired

    def test_cancel_open_order_succeeds(self):
        mgr = self._make_mgr()
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        ok = mgr.cancel(oid)
        assert ok is True
        assert mgr.get_order(oid)["status"] == "cancelled"

    def test_cancel_filled_order_fails(self):
        mgr = self._make_mgr()
        oid = mgr.submit("AAPL", side="buy", quantity=10)
        mgr.simulate_fill(oid, 180.0)
        ok = mgr.cancel(oid)
        assert ok is False

    def test_all_orders_returns_all(self):
        mgr = self._make_mgr()
        for sym in ("AAPL", "TSLA", "NVDA"):
            mgr.submit(sym, side="buy", quantity=10)
        assert len(mgr.all_orders()) == 3

    def test_kill_switch_blocks_submit(self):
        from engine_bridge import OrderManager, RiskLimits, RiskManager, enable_kill_switch, disable_kill_switch

        try:
            enable_kill_switch()
            limits = RiskLimits()
            mgr = OrderManager(RiskManager(limits))
            with pytest.raises(RuntimeError, match="kill-switch"):
                mgr.submit("AAPL", side="buy", quantity=1)
        finally:
            disable_kill_switch()

    def test_kill_switch_can_be_disabled(self):
        from engine_bridge import enable_kill_switch, disable_kill_switch, kill_switch_active

        enable_kill_switch()
        assert kill_switch_active() is True
        disable_kill_switch()
        assert kill_switch_active() is False

    def test_unique_order_ids(self):
        """Each submitted order must get a distinct client order ID."""
        mgr = self._make_mgr()
        ids = {mgr.submit("AAPL", side="buy", quantity=1) for _ in range(20)}
        assert len(ids) == 20
