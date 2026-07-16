/**
 * python_bridge.cpp — pybind11 bindings for the QuantNexus C++ engine.
 *
 * Exposes the following Python classes:
 *
 *   quantnexus_engine.OrderBook         — Level 2 order book
 *   quantnexus_engine.RiskManager       — Pre-trade risk checks
 *   quantnexus_engine.OrderManager      — Order lifecycle + kill-switch
 *   quantnexus_engine.PriceLevel        — (price, volume) struct
 *   quantnexus_engine.BookSnapshot      — Top-N book snapshot
 *
 * Usage from Python::
 *
 *   import quantnexus_engine as qne
 *
 *   book = qne.OrderBook("EUR_USD")
 *   book.apply_snapshot(
 *       bids=[qne.PriceLevel(1.0850, 1e6), qne.PriceLevel(1.0849, 2e6)],
 *       asks=[qne.PriceLevel(1.0851, 500e3), qne.PriceLevel(1.0852, 1.5e6)],
 *   )
 *   snap = book.snapshot(5)
 *   print(snap.best_bid, snap.best_ask)
 *
 *   risk = qne.RiskManager()
 *   mgr  = qne.OrderManager(risk)
 *   oid  = mgr.submit("AAPL", "buy", "limit", 100, limit_price=180.0)
 *   mgr.simulate_fill(oid, 180.0)
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "order_book.h"
#include "order_manager.h"
#include "risk_manager.h"

namespace py = pybind11;
using namespace qn;

PYBIND11_MODULE(quantnexus_engine, m) {
    m.doc() = "QuantNexus C++ execution engine — Python bindings";

    // ── PriceLevel ────────────────────────────────────────────────────────────
    py::class_<PriceLevel>(m, "PriceLevel")
        .def(py::init<Price, Volume>(), py::arg("price"), py::arg("volume"))
        .def_readwrite("price",  &PriceLevel::price)
        .def_readwrite("volume", &PriceLevel::volume)
        .def("__repr__", [](const PriceLevel& pl) {
            return "PriceLevel(price=" + std::to_string(pl.price)
                 + ", volume=" + std::to_string(pl.volume) + ")";
        });

    // ── BookSnapshot ──────────────────────────────────────────────────────────
    py::class_<BookSnapshot>(m, "BookSnapshot")
        .def_readonly("symbol",       &BookSnapshot::symbol)
        .def_readonly("bids",         &BookSnapshot::bids)
        .def_readonly("asks",         &BookSnapshot::asks)
        .def_readonly("timestamp_ns", &BookSnapshot::timestamp_ns)
        .def("best_bid", [](const BookSnapshot& s) -> py::object {
            if (s.bids.empty()) return py::none();
            return py::float_(s.bids[0].price);
        })
        .def("best_ask", [](const BookSnapshot& s) -> py::object {
            if (s.asks.empty()) return py::none();
            return py::float_(s.asks[0].price);
        })
        .def("spread", [](const BookSnapshot& s) -> py::object {
            if (s.bids.empty() || s.asks.empty()) return py::none();
            return py::float_(s.asks[0].price - s.bids[0].price);
        });

    // ── OrderBook ─────────────────────────────────────────────────────────────
    py::class_<OrderBook>(m, "OrderBook")
        .def(py::init<std::string>(), py::arg("symbol"))
        .def("apply_snapshot", &OrderBook::apply_snapshot,
             py::arg("bids"), py::arg("asks"))
        .def("apply_update", &OrderBook::apply_update,
             py::arg("is_bid"), py::arg("price"), py::arg("volume"))
        .def("best_bid",   &OrderBook::best_bid)
        .def("best_ask",   &OrderBook::best_ask)
        .def("mid_price",  &OrderBook::mid_price)
        .def("spread",     &OrderBook::spread)
        .def("snapshot",   &OrderBook::snapshot, py::arg("depth") = 10)
        .def("level_count",&OrderBook::level_count)
        .def_property_readonly("symbol", &OrderBook::symbol);

    // ── RiskLimits ────────────────────────────────────────────────────────────
    py::class_<RiskLimits>(m, "RiskLimits")
        .def(py::init<>())
        .def_readwrite("max_order_notional",  &RiskLimits::max_order_notional)
        .def_readwrite("max_position_size",   &RiskLimits::max_position_size)
        .def_readwrite("max_daily_loss",      &RiskLimits::max_daily_loss)
        .def_readwrite("concentration_limit", &RiskLimits::concentration_limit)
        .def_readwrite("portfolio_nav",       &RiskLimits::portfolio_nav);

    // ── RiskCheckResult ───────────────────────────────────────────────────────
    py::enum_<RiskCheckResult>(m, "RiskCheckResult")
        .value("Approved", RiskCheckResult::Approved)
        .value("Rejected", RiskCheckResult::Rejected)
        .export_values();

    // ── RiskManager ───────────────────────────────────────────────────────────
    py::class_<RiskManager, std::shared_ptr<RiskManager>>(m, "RiskManager")
        .def(py::init<RiskLimits>(), py::arg("limits") = RiskLimits{})
        .def("check", [](RiskManager& rm, const std::string& symbol,
                         int side, double quantity, double price) {
                auto r = rm.check(symbol, side, quantity, price);
                return py::make_tuple(
                    r.result == RiskCheckResult::Approved,
                    r.reason
                );
            },
            py::arg("symbol"), py::arg("side"), py::arg("quantity"), py::arg("price"))
        .def("record_fill",    &RiskManager::record_fill,
             py::arg("symbol"), py::arg("side"), py::arg("quantity"), py::arg("fill_price"))
        .def("record_daily_pnl", &RiskManager::record_daily_pnl, py::arg("delta"))
        .def("update_limits",  &RiskManager::update_limits, py::arg("limits"))
        .def("current_limits", &RiskManager::current_limits)
        .def("add_allowed_symbol",  &RiskManager::add_allowed_symbol, py::arg("symbol"))
        .def("clear_allowed_symbols", &RiskManager::clear_allowed_symbols)
        .def("positions",      &RiskManager::positions)
        .def("daily_pnl",      &RiskManager::daily_pnl);

    // ── OrderSide / OrderType / OrderStatus enums ─────────────────────────────
    py::enum_<OrderSide>(m, "OrderSide")
        .value("Buy",  OrderSide::Buy)
        .value("Sell", OrderSide::Sell)
        .export_values();

    py::enum_<OrderType>(m, "OrderType")
        .value("Market",    OrderType::Market)
        .value("Limit",     OrderType::Limit)
        .value("Stop",      OrderType::Stop)
        .value("StopLimit", OrderType::StopLimit)
        .export_values();

    py::enum_<OrderStatus>(m, "OrderStatus")
        .value("Pending",          OrderStatus::Pending)
        .value("Submitted",        OrderStatus::Submitted)
        .value("PartiallyFilled",  OrderStatus::PartiallyFilled)
        .value("Filled",           OrderStatus::Filled)
        .value("Cancelled",        OrderStatus::Cancelled)
        .value("Rejected",         OrderStatus::Rejected)
        .export_values();

    // ── Order struct ──────────────────────────────────────────────────────────
    py::class_<Order>(m, "Order")
        .def_readonly("client_order_id",  &Order::client_order_id)
        .def_readonly("broker_order_id",  &Order::broker_order_id)
        .def_readonly("symbol",           &Order::symbol)
        .def_readonly("side",             &Order::side)
        .def_readonly("type",             &Order::type)
        .def_readonly("quantity",         &Order::quantity)
        .def_readonly("limit_price",      &Order::limit_price)
        .def_readonly("stop_price",       &Order::stop_price)
        .def_readonly("filled_qty",       &Order::filled_qty)
        .def_readonly("avg_fill_price",   &Order::avg_fill_price)
        .def_readonly("status",           &Order::status)
        .def_readonly("reject_reason",    &Order::reject_reason);

    // ── OrderManager ──────────────────────────────────────────────────────────
    py::class_<OrderManager>(m, "OrderManager")
        .def(py::init<std::shared_ptr<RiskManager>>(), py::arg("risk_manager"))
        .def("submit",
            [](OrderManager& mgr,
               const std::string& symbol,
               const std::string& side_str,
               const std::string& type_str,
               double quantity,
               double limit_price,
               double stop_price) -> std::string
            {
                Order o;
                o.symbol    = symbol;
                o.side      = (side_str == "sell") ? OrderSide::Sell : OrderSide::Buy;
                o.quantity  = quantity;
                o.limit_price = limit_price;
                o.stop_price  = stop_price;
                if      (type_str == "limit")     o.type = OrderType::Limit;
                else if (type_str == "stop")      o.type = OrderType::Stop;
                else if (type_str == "stop_limit") o.type = OrderType::StopLimit;
                else                              o.type = OrderType::Market;
                return mgr.submit(o);
            },
            py::arg("symbol"),
            py::arg("side")       = "buy",
            py::arg("type")       = "market",
            py::arg("quantity")   = 1.0,
            py::arg("limit_price")= 0.0,
            py::arg("stop_price") = 0.0)
        .def("cancel",        &OrderManager::cancel,        py::arg("client_order_id"))
        .def("simulate_fill", &OrderManager::simulate_fill, py::arg("client_order_id"),
             py::arg("fill_price"))
        .def("get_order",     &OrderManager::get_order,     py::arg("client_order_id"))
        .def("all_orders",    &OrderManager::all_orders)
        .def_static("enable_kill_switch",  &OrderManager::enable_kill_switch)
        .def_static("disable_kill_switch", &OrderManager::disable_kill_switch)
        .def_static("kill_switch_active",  &OrderManager::kill_switch_active);

    // ── Module-level kill-switch convenience ──────────────────────────────────
    m.def("enable_kill_switch",  &OrderManager::enable_kill_switch,
          "Halt all order submissions immediately (platform-wide).");
    m.def("disable_kill_switch", &OrderManager::disable_kill_switch,
          "Restore order submissions.");
    m.def("kill_switch_active",  &OrderManager::kill_switch_active,
          "Returns True if the kill-switch is currently active.");
}
