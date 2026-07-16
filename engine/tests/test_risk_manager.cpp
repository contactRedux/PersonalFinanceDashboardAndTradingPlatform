/**
 * test_risk_manager.cpp — Unit tests for the pre-trade risk manager.
 */

#include "risk_manager.h"
#include <gtest/gtest.h>

using namespace qn;

// ── Fixtures ──────────────────────────────────────────────────────────────────

class RiskManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        limits.max_order_notional   = 100'000.0;
        limits.max_position_size    = 1'000.0;
        limits.max_daily_loss       = -10'000.0;
        limits.concentration_limit  = 0.25;
        limits.portfolio_nav        = 1'000'000.0;
        rm = std::make_unique<RiskManager>(limits);
    }

    RiskLimits limits;
    std::unique_ptr<RiskManager> rm;
};

// ── Tests ─────────────────────────────────────────────────────────────────────

TEST_F(RiskManagerTest, ValidOrderIsApproved) {
    auto outcome = rm->check("AAPL", +1, 100.0, 180.0);  // notional = $18,000
    EXPECT_EQ(outcome.result, RiskCheckResult::Approved);
    EXPECT_TRUE(outcome.reason.empty());
}

TEST_F(RiskManagerTest, ExcessiveNotionalIsRejected) {
    // 1000 shares at $200 = $200,000 > limit of $100,000
    auto outcome = rm->check("TSLA", +1, 1000.0, 200.0);
    EXPECT_EQ(outcome.result, RiskCheckResult::Rejected);
    EXPECT_FALSE(outcome.reason.empty());
}

TEST_F(RiskManagerTest, ExcessivePositionSizeRejected) {
    // Buy 1100 shares > max_position_size of 1000
    auto outcome = rm->check("NVDA", +1, 1100.0, 50.0);
    EXPECT_EQ(outcome.result, RiskCheckResult::Rejected);
}

TEST_F(RiskManagerTest, DailyLossLimitRejection) {
    // Simulate a daily loss of -15,000 (below -10,000 limit)
    rm->record_daily_pnl(-15'000.0);
    auto outcome = rm->check("SPY", +1, 1.0, 500.0);
    EXPECT_EQ(outcome.result, RiskCheckResult::Rejected);
}

TEST_F(RiskManagerTest, ConcentrationLimitRejected) {
    // notional = 300,000, portfolio_nav = 1,000,000 → 30% > 25% limit
    auto outcome = rm->check("MSFT", +1, 1000.0, 300.0);
    EXPECT_EQ(outcome.result, RiskCheckResult::Rejected);
}

TEST_F(RiskManagerTest, AllowListBlocksUnlistedSymbol) {
    rm->add_allowed_symbol("AAPL");
    rm->add_allowed_symbol("SPY");

    auto approved = rm->check("AAPL", +1, 10.0, 180.0);
    EXPECT_EQ(approved.result, RiskCheckResult::Approved);

    auto rejected = rm->check("TSLA", +1, 10.0, 200.0);
    EXPECT_EQ(rejected.result, RiskCheckResult::Rejected);
}

TEST_F(RiskManagerTest, EmptyAllowListPermitsAllSymbols) {
    rm->clear_allowed_symbols();
    auto outcome = rm->check("ANYTHING", +1, 1.0, 1.0);
    EXPECT_EQ(outcome.result, RiskCheckResult::Approved);
}

TEST_F(RiskManagerTest, PositionAccumulatesCorrectly) {
    rm->record_fill("AAPL", +1, 100.0, 180.0);
    rm->record_fill("AAPL", +1, 50.0,  181.0);
    rm->record_fill("AAPL", -1, 30.0,  182.0);

    auto pos = rm->positions();
    EXPECT_NEAR(pos.at("AAPL"), 120.0, 1e-9);  // 100 + 50 - 30
}

TEST_F(RiskManagerTest, DailyPnlAccumulates) {
    rm->record_daily_pnl(-1000.0);
    rm->record_daily_pnl(500.0);
    EXPECT_NEAR(rm->daily_pnl(), -500.0, 1e-9);
}

TEST_F(RiskManagerTest, UpdateLimitsIsEffective) {
    RiskLimits new_limits;
    new_limits.max_order_notional = 10.0;  // extremely tight
    rm->update_limits(new_limits);

    auto outcome = rm->check("AAPL", +1, 1.0, 20.0);  // notional = $20 > $10
    EXPECT_EQ(outcome.result, RiskCheckResult::Rejected);
}
