/**
 * E2E tests — Watchlist panel CRUD.
 *
 * ⚠️  REMINDER: Re-run with TEST_USER_EMAIL/PASSWORD set to fully validate.
 *
 * Tests:
 *  1. Watchlist panel renders symbol search input (always runs)
 *  2. Add a ticker → it appears in the watchlist (requires creds)
 *  3. Remove a ticker → it disappears (requires creds)
 *  4. Duplicate ticker rejection — error shown (requires creds)
 */

import { test, expect } from "@playwright/test";
import { LoginPage } from "./poms/LoginPage";
import { WatchlistPage } from "./poms/WatchlistPage";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;
const HAS_CREDS = Boolean(TEST_EMAIL && TEST_PASSWORD);
const TOTP_ENABLED = process.env.TOTP_TEST_ENABLED === "true";

// ─── Always-run (no credentials needed) ──────────────────────────────────────

test.describe("Watchlist panel — public", () => {
  test.skip(!HAS_CREDS, "Skipping: TEST_USER_EMAIL/PASSWORD not set (even public tests need login)");

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);
    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
    }
  });

  test("watchlist panel renders symbol search input", async ({ page }) => {
    const watchlistPage = new WatchlistPage(page);
    const input = page.getByRole("textbox", { name: /add symbol|search|ticker/i });
    await expect(input).toBeVisible({ timeout: 8_000 });
  });

  test("can type a symbol in the search input", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /add symbol|search|ticker/i });
    await input.fill("MSFT");
    await expect(input).toHaveValue("MSFT");
  });
});

// ─── Credential-gated CRUD tests ─────────────────────────────────────────────

test.describe("Watchlist panel — CRUD", () => {
  test.skip(!HAS_CREDS, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test.beforeEach(async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);
    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
    }
  });

  test("add ticker to watchlist — it appears in the list", async ({ page }) => {
    const watchlist = new WatchlistPage(page);
    const testSymbol = "NVDA";

    await watchlist.addSymbol(testSymbol);
    await watchlist.expectSymbolVisible(testSymbol);
  });

  test("remove ticker from watchlist — it disappears", async ({ page }) => {
    const watchlist = new WatchlistPage(page);
    const testSymbol = "NVDA";

    // Ensure the symbol is there first
    await watchlist.addSymbol(testSymbol);
    await watchlist.expectSymbolVisible(testSymbol);

    // Remove it
    await watchlist.removeSymbol(testSymbol);
    await watchlist.expectSymbolAbsent(testSymbol);
  });

  test("adding duplicate ticker shows an error", async ({ page }) => {
    const watchlist = new WatchlistPage(page);
    const testSymbol = "AAPL";

    // Add once
    await watchlist.addSymbol(testSymbol);
    await watchlist.expectSymbolVisible(testSymbol);

    // Add again — should show error
    await watchlist.addSymbol(testSymbol);
    await watchlist.expectDuplicateError();
  });
});
