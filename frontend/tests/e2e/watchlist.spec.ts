/**
 * E2E tests — Watchlist interaction.
 *
 * Skipped unless TEST_USER_EMAIL/PASSWORD are set.
 */

import { test, expect } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;

test.describe("Watchlist panel", () => {
  test.skip(!TEST_EMAIL || !TEST_PASSWORD, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill(TEST_EMAIL!);
    await page.getByRole("textbox", { name: /password/i }).fill(TEST_PASSWORD!);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
  });

  test("watchlist panel renders symbol search input", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /add symbol/i });
    await expect(input).toBeVisible({ timeout: 8000 });
  });

  test("can type a symbol in the search input", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /add symbol/i });
    await input.fill("MSFT");
    await expect(input).toHaveValue("MSFT");
  });
});
