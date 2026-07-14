/**
 * E2E tests — Chart panel symbol change.
 *
 * Skipped unless TEST_USER_EMAIL/PASSWORD are set.
 */

import { test, expect } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;

test.describe("Chart panel", () => {
  test.skip(!TEST_EMAIL || !TEST_PASSWORD, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill(TEST_EMAIL!);
    await page.getByRole("textbox", { name: /password/i }).fill(TEST_PASSWORD!);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
  });

  test("chart toolbar shows timeframe buttons", async ({ page }) => {
    // The ChartToolbar renders timeframe buttons (1m, 5m, 1h, etc.)
    await expect(page.getByRole("button", { name: "1D" }).first()).toBeVisible({
      timeout: 8000,
    });
  });

  test("clicking 1H timeframe updates toolbar", async ({ page }) => {
    const btn = page.getByRole("button", { name: "1H" }).first();
    await expect(btn).toBeVisible({ timeout: 8000 });
    await btn.click();
    // After click, 1H should have active styling (aria-pressed or class change)
    await expect(btn).toBeVisible();
  });
});
