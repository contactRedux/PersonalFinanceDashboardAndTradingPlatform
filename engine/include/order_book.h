#pragma once
/**
 * order_book.h — Lock-free in-memory order book (Level 2).
 *
 * Data Structure
 * ==============
 * Two skip-list–style price level maps (bids descending, asks ascending)
 * backed by std::map with a shared_mutex for reader/writer lock separation.
 *
 * In Phase 2, the shared_mutex will be replaced with a fully lock-free
 * structure (Hazard Pointers + atomic CAS) once benchmarks confirm Python
 * dispatch is the bottleneck.  The interface below is intentionally stable
 * to make that transition transparent to callers.
 *
 * Thread safety
 * =============
 * - Multiple concurrent readers are allowed (shared lock).
 * - A single writer at a time holds an exclusive lock.
 * - All public methods are thread-safe.
 */

#include <atomic>
#include <cstdint>
#include <map>
#include <optional>
#include <shared_mutex>
#include <string>
#include <vector>

namespace qn {

// ── Types ─────────────────────────────────────────────────────────────────────

using Price  = double;   ///< Price level (double for FX pips precision)
using Volume = double;   ///< Aggregate size at a price level

/// Single price level: price → aggregate volume.
struct PriceLevel {
    Price  price;
    Volume volume;
};

/// Top-N bids and asks snapshot.
struct BookSnapshot {
    std::string symbol;
    std::vector<PriceLevel> bids;  ///< Sorted descending by price
    std::vector<PriceLevel> asks;  ///< Sorted ascending by price
    int64_t timestamp_ns;          ///< Wall-clock nanoseconds since epoch
};

// ── OrderBook ─────────────────────────────────────────────────────────────────

/**
 * Thread-safe in-memory order book for a single instrument.
 *
 * Maintains aggregated bid/ask price levels.  Individual order IDs are NOT
 * tracked — the book stores the total volume per price level, which is the
 * standard for market-making and signal-generation use cases.
 */
class OrderBook {
public:
    explicit OrderBook(std::string symbol);

    // ── Mutation ──────────────────────────────────────────────────────────────

    /**
     * Apply a full book snapshot (e.g. from a WebSocket initial snapshot).
     *
     * Replaces the existing book entirely.
     */
    void apply_snapshot(const std::vector<PriceLevel>& bids,
                        const std::vector<PriceLevel>& asks);

    /**
     * Apply a delta update (L2 diff):
     *   volume > 0  → set/update that level
     *   volume == 0 → remove that level
     */
    void apply_update(bool is_bid, Price price, Volume volume);

    // ── Queries ──────────────────────────────────────────────────────────────

    /// Best bid price, or nullopt when the book is empty.
    [[nodiscard]] std::optional<Price> best_bid() const;

    /// Best ask price, or nullopt when the book is empty.
    [[nodiscard]] std::optional<Price> best_ask() const;

    /// Mid-price = (best_bid + best_ask) / 2, or nullopt when either side is absent.
    [[nodiscard]] std::optional<Price> mid_price() const;

    /// Bid-ask spread, or nullopt when either side is absent.
    [[nodiscard]] std::optional<Price> spread() const;

    /// Top-N snapshot (thread-safe copy).
    [[nodiscard]] BookSnapshot snapshot(std::size_t depth = 10) const;

    /// Total number of price levels across both sides.
    [[nodiscard]] std::size_t level_count() const;

    const std::string& symbol() const { return symbol_; }

private:
    std::string symbol_;

    // bids: highest price first  (std::map with reverse comparator)
    using BidMap = std::map<Price, Volume, std::greater<Price>>;
    // asks: lowest price first
    using AskMap = std::map<Price, Volume>;

    BidMap bids_;
    AskMap asks_;

    mutable std::shared_mutex mutex_;
};

}  // namespace qn
