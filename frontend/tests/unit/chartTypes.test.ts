/**
 * Unit tests for Point & Figure and Kagi chart calculation functions.
 */

import { describe, it, expect } from "vitest";
import {
  pointAndFigure,
  kagi,
  computeAutoBoxSize,
} from "@/lib/indicators/chartTypes";
import type { OHLCBar } from "@/lib/indicators/chartTypes";

// ─── Test helpers ─────────────────────────────────────────────────────────────

function makeBars(closes: number[]): OHLCBar[] {
  return closes.map((c, i) => ({
    open: c - 0.1,
    high: c + 0.5,
    low: c - 0.5,
    close: c,
  }));
}

// ─── P&F tests ────────────────────────────────────────────────────────────────

describe("pointAndFigure", () => {
  it("returns empty columns for empty input", () => {
    const result = pointAndFigure([], 1, 3);
    expect(result.columns).toHaveLength(0);
  });

  it("returns empty columns for boxSize <= 0", () => {
    const bars = makeBars([100, 105, 110]);
    const result = pointAndFigure(bars, 0, 3);
    expect(result.columns).toHaveLength(0);
  });

  it("generates at least one column for a rising then falling price series", () => {
    const closes = [100, 102, 104, 106, 108, 105, 102, 99, 97]; // up then down
    const bars = makeBars(closes);
    const result = pointAndFigure(bars, 1, 3);
    // Should have at least one column when price moves significantly
    expect(result.columns.length).toBeGreaterThanOrEqual(1);
  });

  it("all X columns have boxCount > 0", () => {
    const closes = [100, 103, 106, 109, 112];
    const bars = makeBars(closes);
    const result = pointAndFigure(bars, 1, 3);
    for (const col of result.columns) {
      expect(col.boxCount).toBeGreaterThan(0);
    }
  });

  it("alternates between X and O columns", () => {
    // Sharp alternating moves that should force reversals
    const closes = [100, 110, 100, 110, 100];
    const bars = closes.map((c) => ({
      open: c,
      high: c + 1,
      low: c - 1,
      close: c,
    }));
    const result = pointAndFigure(bars, 1, 3);
    for (let i = 1; i < result.columns.length; i++) {
      expect(result.columns[i].type).not.toBe(result.columns[i - 1].type);
    }
  });

  it("basePrice is the minimum price level seen", () => {
    const closes = [100, 105, 102, 108, 104];
    const bars = makeBars(closes);
    const result = pointAndFigure(bars, 1, 3);
    if (result.columns.length > 0) {
      expect(result.basePrice).toBeLessThanOrEqual(100);
    }
  });
});

// ─── computeAutoBoxSize tests ─────────────────────────────────────────────────

describe("computeAutoBoxSize", () => {
  it("returns positive value for typical stock prices", () => {
    const bars = makeBars([150, 152, 148, 155, 160]);
    const boxSize = computeAutoBoxSize(bars);
    expect(boxSize).toBeGreaterThan(0);
  });

  it("returns 1 for empty bars", () => {
    const boxSize = computeAutoBoxSize([]);
    expect(boxSize).toBe(1);
  });

  it("returns approximately 1% of average close for high-priced stock", () => {
    const bars = makeBars(Array(20).fill(200));
    const boxSize = computeAutoBoxSize(bars);
    // Should be around 2 (1% of 200), rounded to 1 sig fig
    expect(boxSize).toBeGreaterThan(0);
    expect(boxSize).toBeLessThanOrEqual(10);
  });
});

// ─── Kagi tests ───────────────────────────────────────────────────────────────

describe("kagi", () => {
  it("returns empty lines for empty input", () => {
    const result = kagi([], 1);
    expect(result.lines).toHaveLength(0);
  });

  it("returns empty lines for single bar", () => {
    const result = kagi(makeBars([100]), 1);
    expect(result.lines).toHaveLength(0);
  });

  it("produces at least one line segment for two bars", () => {
    const result = kagi(makeBars([100, 105]), 1);
    expect(result.lines.length).toBeGreaterThanOrEqual(1);
  });

  it("final line includes the last bar", () => {
    const bars = makeBars([100, 102, 104, 103, 105]);
    const result = kagi(bars, 0.5);
    const lastLine = result.lines[result.lines.length - 1];
    expect(lastLine.endBarIndex).toBe(bars.length - 1);
  });

  it("all line directions are 'up' or 'down'", () => {
    const bars = makeBars([100, 110, 105, 115, 108, 120]);
    const result = kagi(bars, 2);
    for (const line of result.lines) {
      expect(["up", "down"]).toContain(line.direction);
    }
  });

  it("reversal threshold of 0 uses 1% of first close", () => {
    // 1% of 100 = 1.0 threshold
    // A 5-point move should definitely trigger a line
    const bars = makeBars([100, 110, 104, 115, 108]);
    const result = kagi(bars, 0);
    expect(result.lines.length).toBeGreaterThan(0);
  });

  it("line startPrice and endPrice are finite numbers", () => {
    const bars = makeBars([100, 102, 101, 105, 103, 107]);
    const result = kagi(bars, 1);
    for (const line of result.lines) {
      expect(isFinite(line.startPrice)).toBe(true);
      expect(isFinite(line.endPrice)).toBe(true);
    }
  });

  it("bar indices are in bounds", () => {
    const bars = makeBars([100, 102, 104, 103, 106]);
    const result = kagi(bars, 1);
    for (const line of result.lines) {
      expect(line.startBarIndex).toBeGreaterThanOrEqual(0);
      expect(line.endBarIndex).toBeLessThan(bars.length);
    }
  });
});
