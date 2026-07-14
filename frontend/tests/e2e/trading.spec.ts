/**
 * E2E tests — Paper trading order flow.
 *
 * ⚠️  REMINDER: Re-run with TEST_USER_EMAIL/PASSWORD set to fully validate.
 *
 * Tests:
 *  1. Place a paper market buy order
 *  2. Verify order appears in orders panel
 *  3. Cancel the order
 *  4. Verify cancellation status
 */

import { test, expect } from "@playwright/test";
import { LoginPage } from "./poms/LoginPage";
import { OrderEntryPage } from "./poms/OrderEntryPage";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;
const HAS_CREDS = Boolean(TEST_EMAIL && TEST_PASSWORD);
const TOTP_ENABLED = process.env.TOTP_TEST_ENABLED === "true";

test.describe("Trading — paper order flow", () => {
  test.skip(!HAS_CREDS, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);
    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
    }
  });

  test("place a paper market buy order and verify it appears in orders panel", async ({
    page,
  }) => {
    const orderPage = new OrderEntryPage(page);

    // Select AAPL, buy, market order, qty 1
    await orderPage.selectSymbol("AAPL");
    await orderPage.selectSide("buy");
    await orderPage.selectOrderType("market");
    await orderPage.enterQuantity(1);
    await orderPage.submitOrder();

    // Order should appear in the orders table
    await orderPage.expectOrderInTable("AAPL");
  });

  test("cancel an open order and verify cancellation status", async ({ page }) => {
    const orderPage = new OrderEntryPage(page);

    // Place order
    await orderPage.selectSymbol("AAPL");
    await orderPage.selectSide("buy");
    await orderPage.selectOrderType("market");
    await orderPage.enterQuantity(1);
    await orderPage.submitOrder();

    // Wait for it to appear
    await orderPage.expectOrderInTable("AAPL");

    // Cancel it
    await orderPage.cancelOrder("AAPL");

    // Status should update to canceled/cancelled
    await orderPage.expectOrderStatus("AAPL", "cancel");
  });
});
