/**
 * order_manager.cpp — Order lifecycle and kill-switch implementation.
 */

#include "order_manager.h"

#include <chrono>
#include <sstream>
#include <stdexcept>

namespace qn {

// ── Static kill-switch flag ───────────────────────────────────────────────────
std::atomic<bool> OrderManager::kill_switch_{false};

// ── Construction ─────────────────────────────────────────────────────────────

OrderManager::OrderManager(std::shared_ptr<RiskManager> risk_manager)
    : risk_manager_(std::move(risk_manager)) {}

// ── Kill-switch ───────────────────────────────────────────────────────────────

void OrderManager::enable_kill_switch() {
    kill_switch_.store(true, std::memory_order_release);
}

void OrderManager::disable_kill_switch() {
    kill_switch_.store(false, std::memory_order_release);
}

bool OrderManager::kill_switch_active() {
    return kill_switch_.load(std::memory_order_acquire);
}

// ── Submit ────────────────────────────────────────────────────────────────────

std::string OrderManager::submit(const Order& order_template) {
    if (kill_switch_active()) {
        throw std::runtime_error("Order rejected: kill-switch is active");
    }

    // Risk pre-check
    const int side_int = (order_template.side == OrderSide::Buy) ? +1 : -1;
    const double price = (order_template.limit_price > 0.0)
                         ? order_template.limit_price
                         : order_template.stop_price;

    auto outcome = risk_manager_->check(
        order_template.symbol, side_int, order_template.quantity, price);
    if (outcome.result == RiskCheckResult::Rejected) {
        throw std::runtime_error("Risk check failed: " + outcome.reason);
    }

    // Stamp the order
    Order order = order_template;
    order.client_order_id = generate_client_order_id();
    order.status = OrderStatus::Submitted;
    order.created_at_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    order.submitted_at_ns = order.created_at_ns;

    {
        std::lock_guard lock(mutex_);
        orders_[order.client_order_id] = order;
    }

    return order.client_order_id;
}

// ── Cancel ────────────────────────────────────────────────────────────────────

bool OrderManager::cancel(const std::string& client_order_id) {
    std::lock_guard lock(mutex_);
    auto it = orders_.find(client_order_id);
    if (it == orders_.end()) return false;
    auto& order = it->second;
    if (order.status == OrderStatus::Filled ||
        order.status == OrderStatus::Cancelled ||
        order.status == OrderStatus::Rejected)
    {
        return false;
    }
    order.status = OrderStatus::Cancelled;
    return true;
}

// ── Simulated fill ────────────────────────────────────────────────────────────

void OrderManager::simulate_fill(const std::string& client_order_id, double fill_price) {
    Order filled_order;
    {
        std::lock_guard lock(mutex_);
        auto it = orders_.find(client_order_id);
        if (it == orders_.end()) return;
        auto& order = it->second;
        order.filled_qty      = order.quantity;
        order.avg_fill_price  = fill_price;
        order.status          = OrderStatus::Filled;
        order.filled_at_ns    = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
        filled_order = order;
    }
    notify_fill(filled_order);
}

// ── Queries ───────────────────────────────────────────────────────────────────

std::optional<Order> OrderManager::get_order(const std::string& client_order_id) const {
    std::lock_guard lock(mutex_);
    auto it = orders_.find(client_order_id);
    if (it == orders_.end()) return std::nullopt;
    return it->second;
}

std::vector<Order> OrderManager::all_orders() const {
    std::lock_guard lock(mutex_);
    std::vector<Order> result;
    result.reserve(orders_.size());
    for (const auto& [id, order] : orders_) {
        result.push_back(order);
    }
    return result;
}

// ── Fill callback ─────────────────────────────────────────────────────────────

void OrderManager::on_fill(FillCallback cb) {
    std::lock_guard lock(mutex_);
    fill_callbacks_.push_back(std::move(cb));
}

void OrderManager::notify_fill(const Order& order) {
    std::vector<FillCallback> callbacks;
    {
        std::lock_guard lock(mutex_);
        callbacks = fill_callbacks_;
    }
    for (auto& cb : callbacks) {
        cb(order);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

std::string OrderManager::generate_client_order_id() const {
    static std::atomic<uint64_t> counter{0};
    const uint64_t id = counter.fetch_add(1, std::memory_order_relaxed);
    const int64_t now_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    std::ostringstream ss;
    ss << "QN-" << now_ns << "-" << id;
    return ss.str();
}

}  // namespace qn
