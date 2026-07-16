#pragma once
/**
 * risk_manager.h — Pre-trade risk checks.
 *
 * Pre-trade checks (all synchronous, single-call overhead < 500ns):
 *   1. Max order size (notional value)
 *   2. Max position size (per symbol, summed open + pending fills)
 *   3. Max daily loss (mark-to-market unrealised + realised P&L)
 *   4. Concentration limit (single symbol < X% of portfolio)
 *   5. Instrument allow-list (block unsupported symbols)
 *
 * All limits are configurable at construction time and can be updated
 * at runtime via setter methods (protected by a mutex).
 */

#include <atomic>
#include <cstddef>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>

namespace qn {

struct RiskLimits {
    double max_order_notional   = 1'000'000.0;  ///< Per-order notional cap (USD)
    double max_position_size    = 10'000.0;     ///< Per-symbol absolute position (shares/units)
    double max_daily_loss       = -50'000.0;    ///< Maximum allowed daily P&L (negative = loss)
    double concentration_limit  = 0.25;         ///< Max fraction of portfolio in one symbol
    double portfolio_nav        = 1'000'000.0;  ///< Current NAV for concentration check
};

enum class RiskCheckResult { Approved, Rejected };

struct RiskCheckOutcome {
    RiskCheckResult result;
    std::string     reason;  ///< Human-readable rejection reason; empty if approved
};

class RiskManager {
public:
    explicit RiskManager(RiskLimits limits = {});

    /**
     * Run all pre-trade risk checks for a proposed order.
     *
     * @param symbol    Instrument symbol.
     * @param side      +1 for buy, -1 for sell.
     * @param quantity  Absolute number of units.
     * @param price     Estimated execution price (for notional check).
     *
     * Returns Approved if all checks pass, Rejected with a reason otherwise.
     */
    [[nodiscard]] RiskCheckOutcome check(const std::string& symbol,
                                         int side,
                                         double quantity,
                                         double price) const;

    // ── Position tracking (called by OrderManager on fills) ───────────────────

    void record_fill(const std::string& symbol, int side, double quantity, double fill_price);
    void record_daily_pnl(double delta);

    // ── Limit management ──────────────────────────────────────────────────────

    void update_limits(const RiskLimits& limits);
    [[nodiscard]] RiskLimits current_limits() const;

    void add_allowed_symbol(const std::string& symbol);
    void clear_allowed_symbols();  ///< Empty set = all symbols allowed

    // ── Snapshot ──────────────────────────────────────────────────────────────
    [[nodiscard]] std::unordered_map<std::string, double> positions() const;
    [[nodiscard]] double daily_pnl() const;

private:
    RiskLimits                                limits_;
    std::unordered_map<std::string, double>   positions_;     ///< symbol → net position
    std::atomic<double>                       daily_pnl_{0.0};
    std::unordered_set<std::string>           allowed_symbols_;
    mutable std::mutex                        mutex_;
};

}  // namespace qn
