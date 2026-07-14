/**
 * Page Object Model — Watchlist panel.
 */

import { type Page, expect } from "@playwright/test";

export class WatchlistPage {
  private readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async addSymbol(symbol: string): Promise<void> {
    const input = this.page.getByRole("textbox", { name: /add symbol|search|ticker/i });
    await input.fill(symbol);
    // Try Enter key or Add button
    const addButton = this.page.getByRole("button", { name: /add|submit/i });
    if (await addButton.isVisible()) {
      await addButton.click();
    } else {
      await input.press("Enter");
    }
  }

  async expectSymbolVisible(symbol: string): Promise<void> {
    await expect(
      this.page.getByText(symbol.toUpperCase())
    ).toBeVisible({ timeout: 8_000 });
  }

  async removeSymbol(symbol: string): Promise<void> {
    const row = this.page.getByRole("row").filter({ hasText: symbol.toUpperCase() });
    const removeBtn = row.getByRole("button", { name: /remove|delete|×/i });
    if (await removeBtn.isVisible()) {
      await removeBtn.click();
    } else {
      // Try right-click context menu
      await row.click({ button: "right" });
      await this.page.getByRole("menuitem", { name: /remove|delete/i }).click();
    }
  }

  async expectSymbolAbsent(symbol: string): Promise<void> {
    await expect(
      this.page.getByRole("row").filter({ hasText: symbol.toUpperCase() })
    ).not.toBeVisible({ timeout: 5_000 });
  }

  async expectDuplicateError(): Promise<void> {
    await expect(
      this.page.getByText(/already|duplicate|exists/i)
    ).toBeVisible({ timeout: 5_000 });
  }
}
