/**
 * E2E tests — Dashboard load and panel presence.
 *
 * Prerequisites: a running backend at NEXT_PUBLIC_API_URL,
 * and a valid test account seeded in the database.
 *
 * These tests are skipped when the TEST_USER_EMAIL/PASSWORD
 * env vars are not set (standard CI without live API keys).
 */

import { test, expect, type Page } from "@playwright/test";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;

/**
 * Helper: authenticate and get to the dashboard.
 */
async function loginAndNavigate(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByRole("textbox", { name: /email/i }).fill(TEST_EMAIL!);
  await page.getByRole("textbox", { name: /password/i }).fill(TEST_PASSWORD!);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
}

test.describe("Dashboard", () => {
  test.skip(!TEST_EMAIL || !TEST_PASSWORD, "TEST_USER_EMAIL/PASSWORD not set — skipping live dashboard tests");

  test("loads dashboard with primary panels", async ({ page }) => {
    await loginAndNavigate(page);
    // Core panels should appear
    await expect(page.getByText("WATCHLIST").first()).toBeVisible({ timeout: 10_000 });
  });

  test("header shows platform name", async ({ page }) => {
    await loginAndNavigate(page);
    await expect(page.getByText(/quantnexus/i).first()).toBeVisible({ timeout: 5000 });
  });
});
