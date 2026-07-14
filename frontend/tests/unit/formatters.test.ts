/**
 * Unit tests for financial formatter utilities.
 */
import { describe, it, expect } from "vitest";
import {
  formatPrice,
  formatCurrency,
  formatCompact,
  formatPct,
  priceChangeClass,
} from "@/lib/formatters";

describe("formatPrice", () => {
  it("formats a number with 2 decimal places", () => {
    expect(formatPrice(198.45)).toBe("198.45");
  });
  it("returns em dash for null", () => {
    expect(formatPrice(null)).toBe("—");
  });
  it("returns em dash for undefined", () => {
    expect(formatPrice(undefined)).toBe("—");
  });
});

describe("formatCurrency", () => {
  it("formats as USD currency", () => {
    expect(formatCurrency(1234.56)).toBe("$1,234.56");
  });
  it("returns em dash for null", () => {
    expect(formatCurrency(null)).toBe("—");
  });
});

describe("formatCompact", () => {
  it("formats large numbers compactly", () => {
    expect(formatCompact(1_500_000_000)).toMatch(/1\.5B/);
    expect(formatCompact(456_000)).toMatch(/456K/);
  });
});

describe("formatPct", () => {
  it("formats positive percentage with + sign", () => {
    expect(formatPct(1.23)).toContain("+");
    expect(formatPct(1.23)).toContain("1.23");
  });
  it("formats negative percentage with - sign", () => {
    expect(formatPct(-0.45)).toContain("-");
  });
});

describe("priceChangeClass", () => {
  it("returns price-up for positive change", () => {
    expect(priceChangeClass(1.5)).toBe("price-up");
  });
  it("returns price-down for negative change", () => {
    expect(priceChangeClass(-0.5)).toBe("price-down");
  });
  it("returns price-flat for zero", () => {
    expect(priceChangeClass(0)).toBe("price-flat");
  });
  it("returns price-flat for null", () => {
    expect(priceChangeClass(null)).toBe("price-flat");
  });
});
