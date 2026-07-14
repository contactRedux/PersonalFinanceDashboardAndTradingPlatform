/**
 * E2E tests — Authentication flow.
 *
 * ⚠️  REMINDER: These tests skip gracefully without credentials.
 * After deployment, re-run with TEST_USER_EMAIL and TEST_USER_PASSWORD set
 * to fully validate the login, TOTP, and logout flows.
 *
 * Tests:
 *  1. Login page loads with email/password inputs
 *  2. Invalid credentials show an error message
 *  3. Unauthenticated root / dashboard redirect to /login
 *  4. Valid credentials → redirect to /dashboard + token stored (requires creds)
 *  5. TOTP second-factor prompt (requires TOTP_TEST_ENABLED + creds)
 *  6. Logout clears session and redirects to /login (requires creds)
 */

import { test, expect } from "@playwright/test";
import { LoginPage } from "./poms/LoginPage";

const TEST_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD;
const TOTP_ENABLED = process.env.TOTP_TEST_ENABLED === "true";

const HAS_CREDS = Boolean(TEST_EMAIL && TEST_PASSWORD);

// ─── Always-run tests (no credentials needed) ────────────────────────────────

test.describe("Authentication — public", () => {
  test("login page loads with email and password inputs", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.submitButton).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login("wrong@example.com", "wrongpassword");
    await loginPage.expectError();
  });

  test("root path redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });

  test("dashboard is protected — redirects unauthenticated to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });
});

// ─── Credential-gated tests ───────────────────────────────────────────────────

test.describe("Authentication — with credentials", () => {
  test.skip(!HAS_CREDS, "Skipping: TEST_USER_EMAIL/PASSWORD not set");

  test("valid login redirects to dashboard", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);

    // If TOTP is not enabled, should go directly to dashboard
    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
    }
  });

  test("access token is stored after successful login", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);

    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
      // Token should be present in localStorage or cookie
      const token = await page.evaluate(() => {
        return (
          localStorage.getItem("access_token") ??
          localStorage.getItem("token") ??
          document.cookie
        );
      });
      expect(token).toBeTruthy();
    }
  });

  test("TOTP second-factor prompt appears when enabled", async ({ page }) => {
    test.skip(!TOTP_ENABLED, "Skipping: TOTP_TEST_ENABLED not set");
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);
    // After password, TOTP input should appear
    await expect(loginPage.totpInput).toBeVisible({ timeout: 8_000 });
  });

  test("logout clears session and redirects to login", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(TEST_EMAIL!, TEST_PASSWORD!);

    if (!TOTP_ENABLED) {
      await loginPage.expectRedirectToDashboard();
      await loginPage.logout();
      await loginPage.expectRedirectToLogin();

      // Token should be cleared
      const token = await page.evaluate(() =>
        localStorage.getItem("access_token") ?? localStorage.getItem("token")
      );
      expect(token).toBeFalsy();
    }
  });
});
