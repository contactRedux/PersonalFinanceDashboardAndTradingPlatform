/**
 * fix_session_simulated.cpp — Simulated FIX session implementation.
 *
 * Used for development and CI testing without a live FIX broker.
 * Market orders are filled immediately at the submitted price.
 */

#include "fix_session.h"

#include <sstream>

namespace qn {
namespace fix {

FixSessionSimulated::FixSessionSimulated() = default;

void FixSessionSimulated::connect() {
    state_ = SessionState::LoggedOn;
}

void FixSessionSimulated::disconnect() {
    state_ = SessionState::Disconnected;
}

SessionState FixSessionSimulated::state() const {
    return state_;
}

void FixSessionSimulated::on_exec_report(ExecReportCallback cb) {
    exec_cb_ = std::move(cb);
}

std::string FixSessionSimulated::new_order(
    const std::string& symbol,
    char side,
    char ord_type,
    double qty,
    double price,
    double /*stop_price*/,
    char /*time_in_force*/)
{
    std::ostringstream ss;
    ss << "SIM-" << ++cl_ord_counter_;
    const std::string cl_ord_id = ss.str();

    if (exec_cb_ && ord_type == '1') {
        // Market order: immediate simulated fill
        ExecutionReport rep{};
        rep.client_order_id = cl_ord_id;
        rep.exec_id         = "EXEC-" + cl_ord_id;
        rep.symbol          = symbol;
        rep.exec_type       = '2';  // Fill
        rep.ord_status      = '2';  // Filled
        rep.cum_qty         = qty;
        rep.leaves_qty      = 0.0;
        rep.avg_px          = price > 0.0 ? price : 100.0;
        rep.last_px         = rep.avg_px;
        rep.last_qty        = qty;
        exec_cb_(rep);
    } else if (exec_cb_) {
        // Limit / stop: acknowledge as New
        ExecutionReport rep{};
        rep.client_order_id = cl_ord_id;
        rep.exec_id         = "EXEC-" + cl_ord_id;
        rep.symbol          = symbol;
        rep.exec_type       = '0';  // New
        rep.ord_status      = '0';  // New
        rep.cum_qty         = 0.0;
        rep.leaves_qty      = qty;
        rep.avg_px          = 0.0;
        exec_cb_(rep);
    }

    return cl_ord_id;
}

std::string FixSessionSimulated::cancel_order(
    const std::string& orig_cl_ord_id,
    const std::string& symbol,
    char /*side*/)
{
    std::ostringstream ss;
    ss << "CANCEL-" << ++cl_ord_counter_;
    const std::string cl_ord_id = ss.str();

    if (exec_cb_) {
        ExecutionReport rep{};
        rep.client_order_id      = cl_ord_id;
        rep.order_id             = orig_cl_ord_id;
        rep.exec_id              = "EXEC-" + cl_ord_id;
        rep.symbol               = symbol;
        rep.exec_type            = '4';  // Cancelled
        rep.ord_status           = '4';  // Cancelled
        rep.cum_qty              = 0.0;
        rep.leaves_qty           = 0.0;
        exec_cb_(rep);
    }

    return cl_ord_id;
}

}  // namespace fix
}  // namespace qn
