/**
 * test_order_book.cpp — Unit tests for the L2 order book.
 */

#include "order_book.h"
#include <gtest/gtest.h>

using namespace qn;

TEST(OrderBookTest, EmptyBookHasNoBestBidOrAsk) {
    OrderBook book("EUR_USD");
    EXPECT_FALSE(book.best_bid().has_value());
    EXPECT_FALSE(book.best_ask().has_value());
    EXPECT_FALSE(book.mid_price().has_value());
    EXPECT_FALSE(book.spread().has_value());
}

TEST(OrderBookTest, ApplySnapshotSetsBestBidAndAsk) {
    OrderBook book("AAPL");
    book.apply_snapshot(
        {{180.0, 100.0}, {179.9, 200.0}},
        {{180.1, 50.0},  {180.2, 150.0}}
    );
    ASSERT_TRUE(book.best_bid().has_value());
    ASSERT_TRUE(book.best_ask().has_value());
    EXPECT_DOUBLE_EQ(*book.best_bid(), 180.0);
    EXPECT_DOUBLE_EQ(*book.best_ask(), 180.1);
}

TEST(OrderBookTest, MidPriceAndSpread) {
    OrderBook book("SPY");
    book.apply_snapshot({{500.0, 1000.0}}, {{500.1, 1000.0}});
    ASSERT_TRUE(book.mid_price().has_value());
    ASSERT_TRUE(book.spread().has_value());
    EXPECT_NEAR(*book.mid_price(), 500.05, 1e-9);
    EXPECT_NEAR(*book.spread(), 0.1, 1e-9);
}

TEST(OrderBookTest, ApplyUpdateAddsLevel) {
    OrderBook book("BTC_USD");
    book.apply_update(true, 50000.0, 0.5);  // bid
    ASSERT_TRUE(book.best_bid().has_value());
    EXPECT_DOUBLE_EQ(*book.best_bid(), 50000.0);
}

TEST(OrderBookTest, ApplyUpdateWithZeroVolumeRemovesLevel) {
    OrderBook book("TSLA");
    book.apply_snapshot({{250.0, 100.0}}, {{251.0, 100.0}});
    book.apply_update(true, 250.0, 0.0);   // remove bid
    EXPECT_FALSE(book.best_bid().has_value());
}

TEST(OrderBookTest, SnapshotRespectDepth) {
    OrderBook book("NVDA");
    book.apply_snapshot(
        {{900.0, 10}, {899.9, 10}, {899.8, 10}, {899.7, 10}, {899.6, 10}},
        {{900.1, 10}, {900.2, 10}, {900.3, 10}, {900.4, 10}, {900.5, 10}}
    );
    const auto snap = book.snapshot(3);
    EXPECT_EQ(snap.bids.size(), 3u);
    EXPECT_EQ(snap.asks.size(), 3u);
}

TEST(OrderBookTest, BidsOrderedDescending) {
    OrderBook book("META");
    book.apply_snapshot(
        {{300.0, 1}, {298.0, 1}, {299.0, 1}},
        {{301.0, 1}}
    );
    const auto snap = book.snapshot(10);
    ASSERT_EQ(snap.bids.size(), 3u);
    EXPECT_GT(snap.bids[0].price, snap.bids[1].price);
    EXPECT_GT(snap.bids[1].price, snap.bids[2].price);
}

TEST(OrderBookTest, AsksOrderedAscending) {
    OrderBook book("AMZN");
    book.apply_snapshot(
        {{185.0, 1}},
        {{186.0, 1}, {187.0, 1}, {185.5, 1}}
    );
    const auto snap = book.snapshot(10);
    ASSERT_EQ(snap.asks.size(), 3u);
    EXPECT_LT(snap.asks[0].price, snap.asks[1].price);
    EXPECT_LT(snap.asks[1].price, snap.asks[2].price);
}

TEST(OrderBookTest, LevelCount) {
    OrderBook book("GOOG");
    EXPECT_EQ(book.level_count(), 0u);
    book.apply_snapshot({{150.0, 1}}, {{150.1, 1}, {150.2, 1}});
    EXPECT_EQ(book.level_count(), 3u);
}
