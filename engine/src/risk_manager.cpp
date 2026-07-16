/**
 * risk_manager.cpp — Pre-trade risk check implementation.
 */

#include "risk_manager.h"
#include <sstream>
#include <stdexcept>

namespace qn {

RiskManager::RiskManager(RiskLimits limits)
    : limits_(limits) {}

RiskCheckOutcome RiskManager::check(
    const std::string& symbol,
    int side,
    double quantity,
    double price) const
{
    std::lock_guard lock(mutex_);

    // 1. Instrument allow-list
    if (!allowed_symbols_.empty() && allowed_symbols_.find(symbol) == allowed_symbols_.end()) {
        return {RiskCheckResult::Rejected, "Symbol " + symbol + " is not on the allow-list"};
    }

    // 2. Notional value check
    const double notional = quantity * price;
    if (notional > limits_.max_order_notional) {
        std::ostringstream ss;
        ss << "Order notional " << notional << " exceeds limit " << limits_.max_order_notional;
        return {RiskCheckResult::Rejected, ss.str()};
    }

    // 3. Per-symbol position size
    double current_pos = 0.0;
    auto it = positions_.find(symbol);
    if (it != positions_.end()) current_pos = it->second;

    const double projected_pos = current_pos + side * quantity;
    if (std::abs(projected_pos) > limits_.max_position_size) {
        std::ostringstream ss;
        ss << "Projected position " << projected_pos
           << " for " << symbol
           << " exceeds limit " << limits_.max_position_size;
        return {RiskCheckResult::Rejected, ss.str()};
    }

    // 4. Daily loss limit
    const double pnl = daily_pnl_.load(std::memory_order_relaxed);
    if (pnl < limits_.max_daily_loss) {
        std::ostringstream ss;
        ss << "Daily P&L " << pnl << " is below the daily loss limit " << limits_.max_daily_loss;
        return {RiskCheckResult::Rejected, ss.str()};
    }

    // 5. Concentration limit
    if (limits_.portfolio_nav > 0.0) {
        const double fraction = notional / limits_.portfolio_nav;
        if (fraction > limits_.concentration_limit) {
            std::ostringstream ss;
            ss << "Order notional represents " << (fraction * 100.0) << "% of NAV, "
               << "exceeding concentration limit of " << (limits_.concentration_limit * 100.0) << "%";
            return {RiskCheckResult::Rejected, ss.str()};
        }
    }

    return {RiskCheckResult::Approved, ""};
}

void RiskManager::record_fill(const std::string& symbol, int side, double quantity, double fill_price) {
    std::lock_guard lock(mutex_);
    positions_[symbol] += side * quantity;
    // Approximate P&L update: not a full mark-to-market; use record_daily_pnl for that.
    (void)fill_price;
}

void RiskManager::record_daily_pnl(double delta) {
    daily_pnl_.fetch_add(delta, std::memory_order_relaxed);
}

void RiskManager::update_limits(const RiskLimits& limits) {
    std::lock_guard lock(mutex_);
    limits_ = limits;
}

RiskLimits RiskManager::current_limits() const {
    std::lock_guard lock(mutex_);
    return limits_;
}

void RiskManager::add_allowed_symbol(const std::string& symbol) {
    std::lock_guard lock(mutex_);
    allowed_symbols_.insert(symbol);
}

void RiskManager::clear_allowed_symbols() {
    std::lock_guard lock(mutex_);
    allowed_symbols_.clear();
}

std::unordered_map<std::string, double> RiskManager::positions() const {
    std::lock_guard lock(mutex_);
    return positions_;
}

double RiskManager::daily_pnl() const {
    return daily_pnl_.load(std::memory_order_relaxed);
}

}  // namespace qn
