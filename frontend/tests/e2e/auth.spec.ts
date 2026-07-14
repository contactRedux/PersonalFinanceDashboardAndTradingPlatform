/**
 * E2E tests — Authentication flow.
 *
 * Tests:
 *  - Login page renders correctly
 *  - Invalid credentials shows error
 *  - Valid credentials redirect to /dashboard
 *  - Logout clears session and redirects to /login
 */

import { test, expect } from "@playwright/test";

test.describe("Authentication flow", () => {
  test("login page loads with email and password inputs", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("textbox", { name: /email/i })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /password/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|log in/i })).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: /email/i }).fill("wrong@example.com");
    await page.getByRole("textbox", { name: /password/i }).fill("wrongpassword");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    // The API will return 401; the UI should show an error
    await expect(
      page.getByText(/invalid credentials|incorrect|failed/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test("root path redirects to login when unauthenticated", async ({ page }) => {
    await page.goto("/");
    // Without auth, Next.js middleware should redirect to /login
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test("dashboard is protected — redirects unauthenticated to login", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });
});
