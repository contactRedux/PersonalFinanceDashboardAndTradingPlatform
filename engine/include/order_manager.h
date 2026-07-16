#pragma once
/**
 * order_manager.h — Order lifecycle management.
 *
 * Responsibilities
 * ================
 * - Assign client order IDs.
 * - Route orders to the appropriate venue adapter
 *   (Alpaca paper-trading REST, FIX protocol, or simulated fill).
 * - Track order state transitions:
 *     pending → submitted → [partially_filled] → filled | cancelled | rejected
 * - Fire callbacks on fill events for position tracking and P&L.
 *
 * Kill-Switch Integration
 * =======================
 * The OrderManager checks the KillSwitch singleton before submitting any
 * order.  If the kill-switch is active, new orders are rejected immediately
 * with status `rejected` and reason "kill-switch active".
 */

#include "order_book.h"
#include "risk_manager.h"
#include <atomic>
#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <mutex>

namespace qn {

// ── Order types ──────────────────────────────────────────────────────────────

enum class OrderSide   { Buy, Sell };
enum class OrderType   { Market, Limit, Stop, StopLimit };
enum class OrderStatus { Pending, Submitted, PartiallyFilled, Filled, Cancelled, Rejected };

struct Order {
    std::string client_order_id;
    std::string broker_order_id;
    std::string symbol;
    OrderSide   side;
    OrderType   type;
    double      quantity;
    double      limit_price  = 0.0;
    double      stop_price   = 0.0;
    double      filled_qty   = 0.0;
    double      avg_fill_price = 0.0;
    OrderStatus status       = OrderStatus::Pending;
    std::string reject_reason;
    int64_t     created_at_ns;   ///< nanoseconds since epoch
    int64_t     submitted_at_ns = 0;
    int64_t     filled_at_ns    = 0;
};

/// Callback invoked when an order is filled (partially or fully).
using FillCallback = std::function<void(const Order&)>;

// ── OrderManager ─────────────────────────────────────────────────────────────

class OrderManager {
public:
    explicit OrderManager(std::shared_ptr<RiskManager> risk_manager);

    /**
     * Submit an order.
     *
     * Returns the assigned client_order_id.  The actual submission is
     * asynchronous; use `on_fill` to receive fill notifications.
     *
     * Throws std::runtime_error if the kill-switch is active or if
     * risk pre-checks fail.
     */
    std::string submit(const Order& order);

    /**
     * Cancel an open order by its client_order_id.
     *
     * Returns true if the cancel request was accepted (async; the order
     * transitions to Cancelled asynchronously).
     */
    bool cancel(const std::string& client_order_id);

    /**
     * Register a callback that fires on each fill event.
     *
     * Multiple callbacks can be registered; all fire in registration order.
     */
    void on_fill(FillCallback cb);

    /**
     * Simulate an immediate fill (for paper trading / testing).
     *
     * Sets filled_qty = quantity and avg_fill_price = fill_price,
     * then fires all registered fill callbacks.
     */
    void simulate_fill(const std::string& client_order_id, double fill_price);

    /// Returns a copy of the order by client_order_id, or nullopt.
    [[nodiscard]] std::optional<Order> get_order(const std::string& client_order_id) const;

    /// Snapshot of all orders (thread-safe copy).
    [[nodiscard]] std::vector<Order> all_orders() const;

    // ── Kill-switch ───────────────────────────────────────────────────────────
    static void enable_kill_switch();
    static void disable_kill_switch();
    static bool kill_switch_active();

private:
    std::shared_ptr<RiskManager>                 risk_manager_;
    std::unordered_map<std::string, Order>       orders_;
    std::vector<FillCallback>                    fill_callbacks_;
    mutable std::mutex                           mutex_;

    static std::atomic<bool>                     kill_switch_;

    std::string generate_client_order_id() const;
    void notify_fill(const Order& order);
};

}  // namespace qn
