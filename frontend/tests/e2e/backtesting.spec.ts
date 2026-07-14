/**
 * E2E tests — Backtesting strategy builder + run flow.
 *
 * ⚠️  REMINDER: Re-run with TEST_USER_EMAIL/PASSWORD set to fully validate.
 *
 * Tests:
 *  1. Navigate to backtest panel, configure SMA crossover, run backtest
 *  2. Wait for results — equity curve chart renders
 *  3. Metrics table is populated with Sharpe, max drawdown values
 */

import { test, expect } from "@playwright/test";
import { LoginPage } from "./poms/LoginPage";
import { BacktestPage } from "./poms/BacktestPage";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;
const HAS_CREDS = Boolean(TEST_EMAIL && TEST_PASSWORD);
const TOTP_ENABLED = process.env.TOTP_TEST_ENABLED === "true";

test.describe("Backtesting — strategy builder and run", () => {
  test.skip(!HAS_CREDS, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);
    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
    }
  });

  test("configure SMA crossover and run backtest — equity curve renders", async ({
    page,
  }) => {
    const backtestPage = new BacktestPage(page);

    await backtestPage.navigate();

    // Set strategy to SMA crossover
    await backtestPage.selectStrategy("sma_cross");

    // Set date range (1 year)
    await backtestPage.setDateRange("2023-01-01", "2024-01-01");

    // Run the backtest
    await backtestPage.runBacktest();

    // Wait for results to load (up to 30s for data fetch)
    await backtestPage.waitForResults(30_000);

    // Equity curve should be visible
    await backtestPage.expectEquityCurveVisible();
  });

  test("backtest results metrics table is populated", async ({ page }) => {
    const backtestPage = new BacktestPage(page);

    await backtestPage.navigate();
    await backtestPage.selectStrategy("sma_cross");
    await backtestPage.setDateRange("2023-01-01", "2024-01-01");
    await backtestPage.runBacktest();
    await backtestPage.waitForResults(30_000);

    // Metrics table should show key metrics
    await backtestPage.expectMetricsTablePopulated();
  });
});
