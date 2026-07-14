/**
 * Page Object Model — Login page.
 *
 * Encapsulates selectors and actions for the /login route.
 */

import { type Page, expect } from "@playwright/test";

export class LoginPage {
  private readonly page: Page;

  // Selectors
  readonly emailInput;
  readonly passwordInput;
  readonly submitButton;
  readonly errorMessage;
  readonly totpInput;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByRole("textbox", { name: /email/i });
    this.passwordInput = page.getByRole("textbox", { name: /password/i });
    this.submitButton = page.getByRole("button", { name: /sign in|log in/i });
    this.errorMessage = page.getByText(/invalid credentials|incorrect|failed|wrong/i);
    this.totpInput = page.getByRole("textbox", { name: /totp|authenticator|code/i });
  }

  async goto(): Promise<void> {
    await this.page.goto("/login");
    await expect(this.emailInput).toBeVisible({ timeout: 10_000 });
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async enterTotp(code: string): Promise<void> {
    await expect(this.totpInput).toBeVisible({ timeout: 5_000 });
    await this.totpInput.fill(code);
    await this.submitButton.click();
  }

  async expectError(): Promise<void> {
    await expect(this.errorMessage).toBeVisible({ timeout: 8_000 });
  }

  async expectRedirectToDashboard(): Promise<void> {
    await this.page.waitForURL(/\/dashboard/, { timeout: 15_000 });
  }

  async expectRedirectToLogin(): Promise<void> {
    await this.page.waitForURL(/\/login/, { timeout: 10_000 });
  }

  async logout(): Promise<void> {
    // Try to find and click a logout button / user menu
    const logoutButton = this.page.getByRole("button", { name: /log out|sign out/i });
    const userMenu = this.page.getByRole("button", { name: /user|account|profile/i });

    if (await logoutButton.isVisible()) {
      await logoutButton.click();
    } else if (await userMenu.isVisible()) {
      await userMenu.click();
      await this.page.getByRole("menuitem", { name: /log out|sign out/i }).click();
    }
  }
}
