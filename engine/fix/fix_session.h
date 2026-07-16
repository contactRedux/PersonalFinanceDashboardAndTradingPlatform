#pragma once
/**
 * fix_session.h — FIX Protocol Session (QuickFIX/n Integration Stub).
 *
 * This header defines the FixSession interface for FIX 4.2/4.4/5.0 SP2
 * order routing.  The implementation requires:
 *   - QuickFIX/n installed (https://github.com/connamara/quickfixn)
 *     or its C++ counterpart QuickFIX (https://github.com/quickfix/quickfix)
 *   - A valid FIX session configuration file (see examples/fix_session.cfg)
 *   - An institutional brokerage relationship + FIX connectivity onboarding
 *
 * When QuickFIX is NOT found, the implementation falls back to a simulated
 * mode (useful for testing the order flow without a live FIX connection).
 *
 * ADR reference: docs/adr/ADR-012-fix-protocol.md
 *
 * ─── FIX Message Types Used ──────────────────────────────────────────────────
 *   D  — New Order (Single)      → submit a new order
 *   F  — Order Cancel Request    → cancel an open order
 *   G  — Order Cancel/Replace    → modify an open order
 *   8  — Execution Report        → fill / reject / cancel confirmation
 *   j  — Business Message Reject → order rejected by broker
 *
 * ─── QuickFIX Installation ───────────────────────────────────────────────────
 *   macOS:   brew install quickfix
 *   Ubuntu:  apt install libquickfix-dev
 *   From source: https://github.com/quickfix/quickfix
 *
 * ─── CMake Integration ───────────────────────────────────────────────────────
 *   Once QuickFIX is installed, add to engine/CMakeLists.txt:
 *
 *     find_package(QuickFIX REQUIRED)
 *     target_link_libraries(quantnexus_engine_core PRIVATE quickfix)
 *
 * ─── Re-engagement Criteria (from ADR-012) ───────────────────────────────────
 *   1. Institutional brokerage relationship in place
 *   2. Legal/compliance review complete (MiFID II / Reg NMS)
 *   3. Risk management kill-switch tested and deployed
 *   4. C++ engine (F-1/F-2) running in production
 */

#include <functional>
#include <string>
#include <optional>

namespace qn {
namespace fix {

// ── FIX session state ─────────────────────────────────────────────────────────

enum class SessionState {
    Disconnected,
    Connecting,
    Logon,          ///< FIX logon sequence in progress
    LoggedOn,       ///< Session established; ready for order flow
    LoggingOut,
};

// ── Execution report (FIX message type 8) ─────────────────────────────────────

struct ExecutionReport {
    std::string order_id;
    std::string client_order_id;
    std::string exec_id;
    std::string symbol;
    char        exec_type;          ///< '0'=New, '1'=PartFill, '2'=Fill, '4'=Cancelled, '8'=Rejected
    char        ord_status;
    double      cum_qty;
    double      leaves_qty;
    double      avg_px;
    double      last_px;
    double      last_qty;
    std::string text;               ///< Optional reject/info text
};

using ExecReportCallback = std::function<void(const ExecutionReport&)>;

// ── FixSession interface ───────────────────────────────────────────────────────

/**
 * Abstract FIX session interface.
 *
 * Concrete implementations:
 *   - FixSessionQuickFIX (requires QuickFIX library)
 *   - FixSessionSimulated (in-process simulation, no external connectivity)
 */
class FixSession {
public:
    virtual ~FixSession() = default;

    /**
     * Establish the FIX session (sends Logon message).
     * Non-blocking; use on_exec_report to receive fills asynchronously.
     */
    virtual void connect() = 0;

    /**
     * Send a Logout message and close the session.
     */
    virtual void disconnect() = 0;

    [[nodiscard]] virtual SessionState state() const = 0;
    [[nodiscard]] virtual bool is_logged_on() const { return state() == SessionState::LoggedOn; }

    /**
     * Submit a new order (FIX message type D).
     *
     * @param symbol        Instrument symbol (e.g. "AAPL", "EUR/USD").
     * @param side          '1' = Buy, '2' = Sell.
     * @param ord_type      '1'=Market, '2'=Limit, '3'=Stop, '4'=StopLimit.
     * @param qty           Order quantity.
     * @param price         Limit price (required for limit/stop-limit orders).
     * @param stop_price    Stop trigger price (required for stop orders).
     * @param time_in_force '0'=Day, '1'=GTC, '3'=IOC, '4'=FOK.
     *
     * @returns             ClOrdID assigned to this order.
     */
    virtual std::string new_order(
        const std::string& symbol,
        char side,
        char ord_type,
        double qty,
        double price       = 0.0,
        double stop_price  = 0.0,
        char time_in_force = '0') = 0;

    /**
     * Send an Order Cancel Request (FIX message type F).
     *
     * @param orig_cl_ord_id  ClOrdID of the order to cancel.
     * @param symbol          Instrument symbol.
     * @param side            Same side as the original order.
     *
     * @returns               New ClOrdID for the cancel request.
     */
    virtual std::string cancel_order(
        const std::string& orig_cl_ord_id,
        const std::string& symbol,
        char side) = 0;

    /**
     * Register a callback for Execution Reports (FIX message type 8).
     */
    virtual void on_exec_report(ExecReportCallback cb) = 0;
};

// ── Simulated FIX session ─────────────────────────────────────────────────────

/**
 * In-process simulated FIX session for development and testing.
 *
 * Immediately fills market orders; leaves limit orders pending.
 * No network connection required.
 */
class FixSessionSimulated final : public FixSession {
public:
    FixSessionSimulated();

    void connect()    override;
    void disconnect() override;
    [[nodiscard]] SessionState state() const override;

    std::string new_order(
        const std::string& symbol, char side, char ord_type,
        double qty, double price, double stop_price,
        char time_in_force) override;

    std::string cancel_order(
        const std::string& orig_cl_ord_id,
        const std::string& symbol, char side) override;

    void on_exec_report(ExecReportCallback cb) override;

private:
    SessionState state_{SessionState::Disconnected};
    ExecReportCallback exec_cb_;
    uint64_t cl_ord_counter_{0};
};

}  // namespace fix
}  // namespace qn
