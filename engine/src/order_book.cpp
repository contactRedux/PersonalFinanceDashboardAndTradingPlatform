/**
 * order_book.cpp — Implementation of the lock-free in-memory order book.
 *
 * Phase 1: Uses std::shared_mutex for reader/writer separation.
 *          Multiple concurrent readers; single writer.
 *
 * Phase 2 (future): Replace shared_mutex with Hazard Pointers + atomic CAS
 *          for true lock-free behaviour once benchmarks confirm the need.
 */

#include "order_book.h"

#include <chrono>

namespace qn {

OrderBook::OrderBook(std::string symbol)
    : symbol_(std::move(symbol)) {}

void OrderBook::apply_snapshot(
    const std::vector<PriceLevel>& bids,
    const std::vector<PriceLevel>& asks)
{
    std::unique_lock lock(mutex_);
    bids_.clear();
    asks_.clear();
    for (const auto& level : bids) {
        if (level.volume > 0.0)
            bids_[level.price] = level.volume;
    }
    for (const auto& level : asks) {
        if (level.volume > 0.0)
            asks_[level.price] = level.volume;
    }
}

void OrderBook::apply_update(bool is_bid, Price price, Volume volume) {
    std::unique_lock lock(mutex_);
    if (is_bid) {
        if (volume <= 0.0)
            bids_.erase(price);
        else
            bids_[price] = volume;
    } else {
        if (volume <= 0.0)
            asks_.erase(price);
        else
            asks_[price] = volume;
    }
}

std::optional<Price> OrderBook::best_bid() const {
    std::shared_lock lock(mutex_);
    if (bids_.empty()) return std::nullopt;
    return bids_.begin()->first;
}

std::optional<Price> OrderBook::best_ask() const {
    std::shared_lock lock(mutex_);
    if (asks_.empty()) return std::nullopt;
    return asks_.begin()->first;
}

std::optional<Price> OrderBook::mid_price() const {
    std::shared_lock lock(mutex_);
    if (bids_.empty() || asks_.empty()) return std::nullopt;
    return (bids_.begin()->first + asks_.begin()->first) / 2.0;
}

std::optional<Price> OrderBook::spread() const {
    std::shared_lock lock(mutex_);
    if (bids_.empty() || asks_.empty()) return std::nullopt;
    return asks_.begin()->first - bids_.begin()->first;
}

BookSnapshot OrderBook::snapshot(std::size_t depth) const {
    std::shared_lock lock(mutex_);
    BookSnapshot snap;
    snap.symbol = symbol_;
    snap.timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    std::size_t i = 0;
    for (const auto& [price, volume] : bids_) {
        if (i++ >= depth) break;
        snap.bids.push_back({price, volume});
    }
    i = 0;
    for (const auto& [price, volume] : asks_) {
        if (i++ >= depth) break;
        snap.asks.push_back({price, volume});
    }
    return snap;
}

std::size_t OrderBook::level_count() const {
    std::shared_lock lock(mutex_);
    return bids_.size() + asks_.size();
}

}  // namespace qn
