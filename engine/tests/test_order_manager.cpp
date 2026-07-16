/**
 * test_order_manager.cpp — Unit tests for the order manager and kill-switch.
 */

#include "order_manager.h"
#include "risk_manager.h"
#include <gtest/gtest.h>
#include <memory>

using namespace qn;

// ── Fixtures ──────────────────────────────────────────────────────────────────

class OrderManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        OrderManager::disable_kill_switch();  // ensure clean state
        RiskLimits limits;
        limits.max_order_notional = 1'000'000.0;
        limits.max_position_size  = 100'000.0;
        limits.max_daily_loss     = -1'000'000.0;
        limits.portfolio_nav      = 100'000'000.0;
        risk = std::make_shared<RiskManager>(limits);
        mgr  = std::make_unique<OrderManager>(risk);
    }

    void TearDown() override {
        OrderManager::disable_kill_switch();  // cleanup
    }

    std::shared_ptr<RiskManager> risk;
    std::unique_ptr<OrderManager> mgr;

    Order make_market_order(const std::string& sym = "AAPL",
                            double qty            = 10.0)
    {
        Order o;
        o.symbol   = sym;
        o.side     = OrderSide::Buy;
        o.type     = OrderType::Market;
        o.quantity = qty;
        return o;
    }
};

// ── Tests ─────────────────────────────────────────────────────────────────────

TEST_F(OrderManagerTest, SubmitReturnsNonEmptyClientOrderId) {
    const auto id = mgr->submit(make_market_order());
    EXPECT_FALSE(id.empty());
}

TEST_F(OrderManagerTest, SubmittedOrderIsRetrievable) {
    const auto id    = mgr->submit(make_market_order());
    const auto order = mgr->get_order(id);
    ASSERT_TRUE(order.has_value());
    EXPECT_EQ(order->status, OrderStatus::Submitted);
}

TEST_F(OrderManagerTest, SimulateFillUpdatesStatus) {
    const auto id = mgr->submit(make_market_order());
    mgr->simulate_fill(id, 180.0);
    const auto order = mgr->get_order(id);
    ASSERT_TRUE(order.has_value());
    EXPECT_EQ(order->status, OrderStatus::Filled);
    EXPECT_DOUBLE_EQ(order->avg_fill_price, 180.0);
    EXPECT_DOUBLE_EQ(order->filled_qty, 10.0);
}

TEST_F(OrderManagerTest, FillCallbackFires) {
    bool callback_fired = false;
    mgr->on_fill([&](const Order& o) {
        callback_fired = (o.status == OrderStatus::Filled);
    });
    const auto id = mgr->submit(make_market_order());
    mgr->simulate_fill(id, 100.0);
    EXPECT_TRUE(callback_fired);
}

TEST_F(OrderManagerTest, CancelOpenOrderSucceeds) {
    const auto id = mgr->submit(make_market_order());
    const bool ok = mgr->cancel(id);
    EXPECT_TRUE(ok);
    const auto order = mgr->get_order(id);
    ASSERT_TRUE(order.has_value());
    EXPECT_EQ(order->status, OrderStatus::Cancelled);
}

TEST_F(OrderManagerTest, CancelFilledOrderFails) {
    const auto id = mgr->submit(make_market_order());
    mgr->simulate_fill(id, 100.0);
    const bool ok = mgr->cancel(id);
    EXPECT_FALSE(ok);
}

TEST_F(OrderManagerTest, AllOrdersReturnsAll) {
    mgr->submit(make_market_order("AAPL"));
    mgr->submit(make_market_order("TSLA"));
    mgr->submit(make_market_order("NVDA"));
    EXPECT_EQ(mgr->all_orders().size(), 3u);
}

TEST_F(OrderManagerTest, KillSwitchBlocksSubmit) {
    OrderManager::enable_kill_switch();
    EXPECT_TRUE(OrderManager::kill_switch_active());
    EXPECT_THROW(mgr->submit(make_market_order()), std::runtime_error);
    OrderManager::disable_kill_switch();
    EXPECT_FALSE(OrderManager::kill_switch_active());
}

TEST_F(OrderManagerTest, KillSwitchCanBeDisabled) {
    OrderManager::enable_kill_switch();
    OrderManager::disable_kill_switch();
    EXPECT_FALSE(OrderManager::kill_switch_active());
    // Submit should succeed after kill-switch is disabled
    EXPECT_NO_THROW(mgr->submit(make_market_order()));
}
