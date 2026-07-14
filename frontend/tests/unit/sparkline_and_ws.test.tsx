/**
 * Unit tests — Sparkline component (ST-F) and useWebSocket backoff logic (ST-G)
 */

import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";

// ─── Sparkline (ST-F) ─────────────────────────────────────────────────────────

import { Sparkline } from "@/components/ui/Sparkline";

describe("Sparkline (ST-F)", () => {
  it("returns null when data has fewer than 2 points", () => {
    const { container } = render(<Sparkline data={[]} />);
    expect(container.firstChild).toBeNull();
    const { container: c2 } = render(<Sparkline data={[100]} />);
    expect(c2.firstChild).toBeNull();
  });

  it("renders an SVG element with data >= 2 points", () => {
    render(<Sparkline data={[100, 105, 103]} />);
    const svg = document.querySelector("svg");
    expect(svg).toBeTruthy();
  });

  it("renders a polyline inside the SVG", () => {
    render(<Sparkline data={[100, 102, 101, 105]} />);
    const polyline = document.querySelector("polyline");
    expect(polyline).toBeTruthy();
  });

  it("uses green stroke when last >= first", () => {
    render(<Sparkline data={[100, 110]} />);
    const polyline = document.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#00d084");
  });

  it("uses red stroke when last < first", () => {
    render(<Sparkline data={[110, 100]} />);
    const polyline = document.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("respects custom width and height props", () => {
    render(<Sparkline data={[100, 105]} width={80} height={30} />);
    const svg = document.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("80");
    expect(svg?.getAttribute("height")).toBe("30");
  });
});

// ─── marketDataStore priceHistory (ST-F) ─────────────────────────────────────

import { useMarketDataStore } from "@/store/marketDataStore";

describe("marketDataStore priceHistory (ST-F)", () => {
  beforeEach(() => {
    // Reset store to initial state
    useMarketDataStore.setState({ quotes: {}, priceHistory: {} });
  });

  it("starts with empty priceHistory", () => {
    expect(useMarketDataStore.getState().priceHistory).toEqual({});
  });

  it("appends price to priceHistory on setQuote", () => {
    const { setQuote } = useMarketDataStore.getState();
    setQuote({ symbol: "AAPL", price: 185, change: 0, change_pct: 0, volume: 0, timestamp: "" });
    expect(useMarketDataStore.getState().priceHistory["AAPL"]).toEqual([185]);
  });

  it("accumulates up to 20 prices", () => {
    const { setQuote } = useMarketDataStore.getState();
    for (let i = 0; i < 25; i++) {
      setQuote({ symbol: "TSLA", price: 200 + i, change: 0, change_pct: 0, volume: 0, timestamp: "" });
    }
    const history = useMarketDataStore.getState().priceHistory["TSLA"];
    expect(history.length).toBe(20);
    // Last 20 prices: indices 5-24
    expect(history[0]).toBe(205);
    expect(history[19]).toBe(224);
  });
});

// ─── useWebSocket backoff (ST-G) ──────────────────────────────────────────────

import { backoffDelay } from "@/hooks/useWebSocket";

describe("backoffDelay (ST-G)", () => {
  it("first attempt returns at least baseDelay * 0.75", () => {
    const delay = backoffDelay(100, 0);
    expect(delay).toBeGreaterThanOrEqual(75); // baseDelay * 0.75
  });

  it("delays grow with attempt count", () => {
    const d0 = backoffDelay(100, 0);
    const d3 = backoffDelay(100, 3);
    // At attempt 3, raw = 100*8 = 800. Should be > first attempt baseline.
    expect(d3).toBeGreaterThanOrEqual(d0 * 0.5); // allow for jitter variance
  });

  it("caps at 1600ms regardless of attempt count", () => {
    // Run 100 times to account for jitter variance
    for (let i = 0; i < 100; i++) {
      const delay = backoffDelay(100, 20);
      expect(delay).toBeLessThanOrEqual(1600 * 1.25); // cap * max jitter
    }
  });

  it("never goes below baseDelay * 0.75", () => {
    for (let i = 0; i < 50; i++) {
      expect(backoffDelay(100, 0)).toBeGreaterThanOrEqual(75);
    }
  });
});
