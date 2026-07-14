/**
 * Page Object Model — Order Entry panel.
 *
 * Encapsulates selectors and actions for the OrderEntryPanel component.
 */

import { type Page, expect } from "@playwright/test";

export class OrderEntryPage {
  private readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async selectSymbol(symbol: string): Promise<void> {
    const symbolInput = this.page.getByRole("textbox", { name: /symbol|ticker/i });
    await symbolInput.clear();
    await symbolInput.fill(symbol);
  }

  async selectSide(side: "buy" | "sell"): Promise<void> {
    const btn = this.page.getByRole("button", { name: new RegExp(side, "i") });
    await btn.click();
  }

  async selectOrderType(type: "market" | "limit" | "stop"): Promise<void> {
    const selector = this.page.getByRole("combobox", { name: /order type|type/i });
    if (await selector.isVisible()) {
      await selector.selectOption(type);
    } else {
      await this.page.getByRole("button", { name: new RegExp(type, "i") }).click();
    }
  }

  async enterQuantity(qty: number): Promise<void> {
    const qtyInput = this.page.getByRole("spinbutton", { name: /quantity|qty|shares/i });
    await qtyInput.clear();
    await qtyInput.fill(String(qty));
  }

  async submitOrder(): Promise<void> {
    await this.page
      .getByRole("button", { name: /place order|submit|buy|sell/i })
      .click();
  }

  async expectOrderInTable(symbol: string): Promise<void> {
    await expect(
      this.page.getByText(symbol.toUpperCase())
    ).toBeVisible({ timeout: 15_000 });
  }

  async cancelOrder(symbol: string): Promise<void> {
    // Find the row with the symbol and click cancel
    const row = this.page.getByRole("row").filter({ hasText: symbol.toUpperCase() });
    const cancelBtn = row.getByRole("button", { name: /cancel/i });
    await cancelBtn.click();
  }

  async expectOrderStatus(symbol: string, status: string): Promise<void> {
    const row = this.page.getByRole("row").filter({ hasText: symbol.toUpperCase() });
    await expect(row.getByText(new RegExp(status, "i"))).toBeVisible({ timeout: 10_000 });
  }
}
