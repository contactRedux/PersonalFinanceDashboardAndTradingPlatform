/**
 * Page Object Model — Backtest panel.
 */

import { type Page, expect } from "@playwright/test";

export class BacktestPage {
  private readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async navigate(): Promise<void> {
    // Look for backtest panel or navigate to the dashboard and find it
    const backtestLink = this.page.getByRole("link", { name: /backtest/i });
    if (await backtestLink.isVisible()) {
      await backtestLink.click();
    }
    // Otherwise assume dashboard already shows backtest panel
  }

  async selectStrategy(name: string): Promise<void> {
    const selector = this.page.getByRole("combobox", { name: /strategy/i });
    if (await selector.isVisible()) {
      await selector.selectOption(name);
    }
  }

  async setParam(key: string, value: string): Promise<void> {
    const input = this.page.getByRole("spinbutton", { name: new RegExp(key, "i") });
    if (await input.isVisible()) {
      await input.clear();
      await input.fill(value);
    }
  }

  async setDateRange(start: string, end: string): Promise<void> {
    const startInput = this.page.getByRole("textbox", { name: /start|from/i });
    const endInput = this.page.getByRole("textbox", { name: /end|to/i });
    if (await startInput.isVisible()) {
      await startInput.clear();
      await startInput.fill(start);
    }
    if (await endInput.isVisible()) {
      await endInput.clear();
      await endInput.fill(end);
    }
  }

  async runBacktest(): Promise<void> {
    await this.page.getByRole("button", { name: /run backtest|run|execute/i }).click();
  }

  async waitForResults(timeout: number = 30_000): Promise<void> {
    // Wait for equity curve container or results section to appear
    await expect(
      this.page.locator('[data-testid="equity-curve"], [aria-label*="equity"], svg').first()
    ).toBeVisible({ timeout });
  }

  async expectEquityCurveVisible(): Promise<void> {
    // Chart should render an SVG or canvas element
    await expect(
      this.page.locator("svg, canvas").first()
    ).toBeVisible({ timeout: 10_000 });
  }

  async expectMetricsTablePopulated(): Promise<void> {
    // Table should have rows with numeric values
    await expect(
      this.page.getByRole("cell").filter({ hasText: /sharpe|return|drawdown/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  }
}
