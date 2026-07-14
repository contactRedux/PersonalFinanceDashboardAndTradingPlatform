/**
 * panels_st10.test.tsx — smoke + behavior tests for ST-10 panels.
 *
 * All API helpers are mocked so tests run fully offline.
 * Panels tested:
 *   ScreenerPanel, AlertsPanel, MacroPanel, HeatMapPanel,
 *   CorrelationMatrixPanel, EconomicCalendarPanel, DarkPoolPanel, CryptoPanel
 */

import React, { act } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// ─── Mock all API modules ─────────────────────────────────────────────────────
vi.mock("@/lib/api/screener", () => ({
  runScreener: vi.fn().mockResolvedValue({
    results: [
      { symbol: "AAPL", name: "Apple Inc", sector: "Technology", market_cap: 3_000_000, price: 185.5, change_pct_1d: 1.2, pe_ratio: 28.5, volume_ratio: 1.4, rsi_14: 62 },
      { symbol: "MSFT", name: "Microsoft", sector: "Technology", market_cap: 2_800_000, price: 380.0, change_pct_1d: 0.8, pe_ratio: 35.2, volume_ratio: 1.1, rsi_14: 58 },
    ],
    count: 2,
    total_universe: 30,
  }),
  getScreenerPresets: vi.fn().mockResolvedValue({
    presets: [
      { id: "value", name: "Value Stocks", description: "Low P/E", conditions: [{ field: "pe_ratio", op: "lt", value: 15 }], logic: "AND" },
      { id: "momentum", name: "Momentum", description: "Strong RSI", conditions: [{ field: "rsi_14", op: "gt", value: 60 }], logic: "AND" },
    ],
  }),
  getSectorMap: vi.fn().mockResolvedValue({
    sectors: [
      {
        sector: "Technology",
        symbols: ["AAPL", "MSFT"],
        avg_change_pct: 1.5,
        stocks: [
          { symbol: "AAPL", name: "Apple Inc", change_pct_1d: 2.0, market_cap: 3_000_000 },
          { symbol: "MSFT", name: "Microsoft", change_pct_1d: 1.0, market_cap: 2_800_000 },
        ],
      },
      {
        sector: "Healthcare",
        symbols: ["JNJ"],
        avg_change_pct: -0.5,
        stocks: [
          { symbol: "JNJ", name: "Johnson & Johnson", change_pct_1d: -0.5, market_cap: 400_000 },
        ],
      },
    ],
  }),
  getCorrelations: vi.fn().mockResolvedValue({
    symbols: ["AAPL", "MSFT", "SPY"],
    matrix: [
      [1.0, 0.85, 0.72],
      [0.85, 1.0, 0.68],
      [0.72, 0.68, 1.0],
    ],
    note: "demo",
  }),
  listAlerts: vi.fn().mockResolvedValue({
    alerts: [
      { id: "a1", user_id: "u1", alert_type: "price_above", symbol: "AAPL", threshold: 200, label: "AAPL breakout", status: "active", created_at: "2025-01-01T00:00:00Z" },
      { id: "a2", user_id: "u1", alert_type: "rsi_below", symbol: "MSFT", threshold: 30, label: "MSFT oversold", status: "triggered", created_at: "2025-01-02T00:00:00Z" },
    ],
  }),
  createAlert: vi.fn().mockResolvedValue({ id: "a3", status: "active" }),
  deleteAlert: vi.fn().mockResolvedValue({ success: true }),
  acknowledgeAlert: vi.fn().mockResolvedValue({ id: "a2", status: "active" }),
  getAlertTypes: vi.fn().mockResolvedValue({
    types: [
      { value: "price_above", label: "Price Above" },
      { value: "price_below", label: "Price Below" },
      { value: "rsi_above", label: "RSI Above" },
      { value: "rsi_below", label: "RSI Below" },
    ],
  }),
  getMacroIndicators: vi.fn().mockResolvedValue({
    as_of: "2025-01-01",
    fed_funds_rate: { value: 5.33, label: "Fed Funds Rate", unit: "%" },
    cpi:            { value: 3.1,  label: "CPI YoY",        unit: "%" },
    gdp:            { value: 2.8,  label: "GDP Growth",     unit: "%" },
    unemployment:   { value: 3.7,  label: "Unemployment",   unit: "%" },
    dxy:            { value: 104.2, label: "DXY Index",     unit: "" },
  }),
  getYieldCurve: vi.fn().mockResolvedValue({
    curve: [
      { maturity: "1M", yield: 5.3 },
      { maturity: "3M", yield: 5.35 },
      { maturity: "2Y", yield: 4.7 },
      { maturity: "10Y", yield: 4.3 },
      { maturity: "30Y", yield: 4.5 },
    ],
    inverted: true,
    spread_10y_2y: -0.4,
    as_of: "2025-01-01",
  }),
  getVix: vi.fn().mockResolvedValue({ value: 14.5, regime: "low_volatility", as_of: "2025-01-01" }),
  getCalendarEvents: vi.fn().mockResolvedValue({
    events: [
      { id: "ev1", date: "2025-02-07", time: "14:00", currency: "USD", impact: "high",   event: "FOMC Meeting",  actual: null, forecast: null, previous: null, is_upcoming: true, days_until: 2 },
      { id: "ev2", date: "2025-02-13", time: "08:30", currency: "USD", impact: "high",   event: "CPI Report",    actual: null, forecast: "3.0%", previous: "3.1%", is_upcoming: true, days_until: 8 },
      { id: "ev3", date: "2025-02-14", time: "08:30", currency: "USD", impact: "medium", event: "Retail Sales",  actual: null, forecast: null, previous: null, is_upcoming: true, days_until: 9 },
    ],
    count: 3,
    as_of: "2025-01-01",
  }),
  getFundingRates: vi.fn().mockResolvedValue({
    rates: [
      { symbol: "BTCUSDT", funding_rate: 0.0102, next_funding_time: "2025-01-01T08:00:00Z", mark_price: 45000 },
      { symbol: "ETHUSDT", funding_rate: -0.0045, next_funding_time: "2025-01-01T08:00:00Z", mark_price: 2500 },
    ],
    as_of: "2025-01-01",
  }),
  getCryptoTopMovers: vi.fn().mockResolvedValue({
    movers: [
      { symbol: "BTC", name: "Bitcoin",   price: 45_000, change_24h:  3.2, volume_24h: 28_000_000_000, market_cap: null },
      { symbol: "ETH", name: "Ethereum",  price:  2_500, change_24h: -1.5, volume_24h: 14_000_000_000, market_cap: null },
      { symbol: "SOL", name: "Solana",    price:   98.5, change_24h:  5.8, volume_24h:  3_000_000_000, market_cap: null },
      { symbol: "AVAX", name: "Avalanche", price:  35.2, change_24h: -2.1, volume_24h:    800_000_000, market_cap: null },
    ],
    as_of: "2025-01-01",
  }),
  getCryptoOnchain: vi.fn().mockResolvedValue({
    symbol: "BTC",
    metrics: {
      price: 45_000,
      market_cap: 880_000_000_000,
      volume_24h: 28_000_000_000,
      change_24h: 3.2,
      ath: 69_000,
      ath_change_pct: -34.8,
    },
    as_of: "2025-01-01",
  }),
}));

vi.mock("@/lib/api/options", () => ({
  getUnusualActivity: vi.fn().mockResolvedValue({
    activity: [
      { symbol: "NVDA", contract_type: "call", strike: 550, expiry: "2025-02-21", premium: 4_200_000, volume: 8_420, open_interest: 12_500, timestamp: new Date().toISOString() },
      { symbol: "SPY",  contract_type: "put",  strike: 490, expiry: "2025-02-07", premium: 3_800_000, volume: 15_200, open_interest: 48_000, timestamp: new Date().toISOString() },
    ],
  }),
}));

vi.mock("@/lib/api/websocket", () => ({
  WS_URLS: { alerts: () => "ws://localhost:8000/ws/alerts/test-user" },
}));

// ─── Import panels under test ─────────────────────────────────────────────────
import { ScreenerPanel } from "@/components/panels/ScreenerPanel";
import { AlertsPanel } from "@/components/panels/AlertsPanel";
import { MacroPanel } from "@/components/panels/MacroPanel";
import { HeatMapPanel } from "@/components/panels/HeatMapPanel";
import { CorrelationMatrixPanel } from "@/components/panels/CorrelationMatrixPanel";
import { EconomicCalendarPanel } from "@/components/panels/EconomicCalendarPanel";
import { DarkPoolPanel } from "@/components/panels/DarkPoolPanel";
import { CryptoPanel } from "@/components/panels/CryptoPanel";

// ─── ScreenerPanel ────────────────────────────────────────────────────────────
describe("ScreenerPanel", () => {
  it("renders panel title SCREENER", async () => {
    await act(async () => { render(<ScreenerPanel />); });
    expect(screen.getByText("SCREENER")).toBeInTheDocument();
  });

  it("renders default filter field select", async () => {
    await act(async () => { render(<ScreenerPanel />); });
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThanOrEqual(2); // field + operator + logic
  });

  it("renders AND/OR logic selector", async () => {
    await act(async () => { render(<ScreenerPanel />); });
    const logicSelect = screen.getByRole("combobox", { name: /logic/i });
    expect(logicSelect).toHaveValue("AND");
  });

  it("renders ▶ SCAN run button", async () => {
    await act(async () => { render(<ScreenerPanel />); });
    expect(screen.getByRole("button", { name: /▶ scan/i })).toBeInTheDocument();
  });

  it("renders + Add Filter button", async () => {
    await act(async () => { render(<ScreenerPanel />); });
    expect(screen.getByRole("button", { name: /add filter/i })).toBeInTheDocument();
  });

  it("loads results when ▶ SCAN is clicked", async () => {
    render(<ScreenerPanel />);
    fireEvent.click(screen.getByRole("button", { name: /▶ scan/i }));
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("shows 2 matches label after scan", async () => {
    render(<ScreenerPanel />);
    fireEvent.click(screen.getByRole("button", { name: /▶ scan/i }));
    await waitFor(() => {
      expect(screen.getByText(/2 matches/i)).toBeInTheDocument();
    });
  });

  it("loads presets when PRESETS is clicked", async () => {
    render(<ScreenerPanel />);
    fireEvent.click(screen.getByRole("button", { name: /presets/i }));
    await waitFor(() => {
      expect(screen.getByText(/value stocks/i)).toBeInTheDocument();
    });
  });

  it("adds a condition row when + Add Filter is clicked", () => {
    render(<ScreenerPanel />);
    const initialCount = screen.getAllByRole("combobox").length;
    fireEvent.click(screen.getByRole("button", { name: /add filter/i }));
    // New condition row adds 2 more selects (field + operator)
    expect(screen.getAllByRole("combobox").length).toBeGreaterThan(initialCount);
  });
});

// ─── AlertsPanel ─────────────────────────────────────────────────────────────
describe("AlertsPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", class MockWS {
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      close() {}
      send() {}
    });
  });

  it("renders panel title ALERT MANAGER", async () => {
    await act(async () => { render(<AlertsPanel />); });
    expect(screen.getByText("ALERT MANAGER")).toBeInTheDocument();
  });

  it("shows MY ALERTS and + NEW tabs", async () => {
    await act(async () => { render(<AlertsPanel />); });
    expect(screen.getByRole("button", { name: /my alerts/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ new/i })).toBeInTheDocument();
  });

  it("loads and renders alert list items", async () => {
    render(<AlertsPanel />);
    await waitFor(() => {
      expect(screen.getByText(/aapl breakout/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/msft oversold/i)).toBeInTheDocument();
  });

  it("shows ACK button for triggered alert", async () => {
    render(<AlertsPanel />);
    await waitFor(() => {
      // triggered alert renders an ACK button
      expect(screen.getByRole("button", { name: /ack/i })).toBeInTheDocument();
    });
  });

  it("switches to + NEW tab on click", async () => {
    render(<AlertsPanel />);
    await waitFor(() => screen.getByText(/aapl breakout/i));
    fireEvent.click(screen.getByRole("button", { name: /\+ new/i }));
    await waitFor(() => {
      // Create form has a Create Alert submit button
      expect(screen.getByRole("button", { name: /create alert/i })).toBeInTheDocument();
    });
  });
});

// ─── MacroPanel ───────────────────────────────────────────────────────────────
describe("MacroPanel", () => {
  it("renders panel title MACRO OVERVIEW", async () => {
    await act(async () => { render(<MacroPanel />); });
    expect(screen.getByText("MACRO OVERVIEW")).toBeInTheDocument();
  });

  it("shows VIX value after load", async () => {
    render(<MacroPanel />);
    await waitFor(() => {
      expect(screen.getByText("14.50")).toBeInTheDocument();
    });
  });

  it("shows Fed Funds Rate label from indicators", async () => {
    render(<MacroPanel />);
    await waitFor(() => {
      expect(screen.getByText("Fed Funds Rate")).toBeInTheDocument();
    });
  });

  it("shows CPI YoY label", async () => {
    render(<MacroPanel />);
    await waitFor(() => {
      expect(screen.getByText("CPI YoY")).toBeInTheDocument();
    });
  });

  it("renders SVG yield curve chart", async () => {
    render(<MacroPanel />);
    await waitFor(() => {
      expect(document.querySelector("svg")).toBeInTheDocument();
    });
  });

  it("shows inverted yield curve warning banner", async () => {
    render(<MacroPanel />);
    await waitFor(() => {
      expect(screen.getByText(/inverted/i)).toBeInTheDocument();
    });
  });
});

// ─── HeatMapPanel ────────────────────────────────────────────────────────────
describe("HeatMapPanel", () => {
  it("renders panel title SECTOR HEAT MAP", async () => {
    await act(async () => { render(<HeatMapPanel />); });
    expect(screen.getByText("SECTOR HEAT MAP")).toBeInTheDocument();
  });

  it("renders SVG treemap after data loads", async () => {
    render(<HeatMapPanel />);
    await waitFor(() => {
      expect(document.querySelector("svg")).toBeInTheDocument();
    });
  });

  it("renders sector legend labels", async () => {
    render(<HeatMapPanel />);
    await waitFor(() => {
      expect(screen.getByText(/technology/i)).toBeInTheDocument();
    });
  });

  it("renders stock symbol cells inside SVG", async () => {
    render(<HeatMapPanel />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
  });
});

// ─── CorrelationMatrixPanel ───────────────────────────────────────────────────
describe("CorrelationMatrixPanel", () => {
  it("renders panel title CORRELATION MATRIX", async () => {
    await act(async () => { render(<CorrelationMatrixPanel />); });
    expect(screen.getByText("CORRELATION MATRIX")).toBeInTheDocument();
  });

  it("renders symbol input field", async () => {
    await act(async () => { render(<CorrelationMatrixPanel />); });
    const input = screen.getByRole("textbox", { name: /symbols/i });
    expect(input).toBeInTheDocument();
  });

  it("renders GO apply button", async () => {
    await act(async () => { render(<CorrelationMatrixPanel />); });
    expect(screen.getByRole("button", { name: /go/i })).toBeInTheDocument();
  });

  it("shows symbol headers after load", async () => {
    render(<CorrelationMatrixPanel />);
    await waitFor(() => {
      expect(screen.getAllByText("AAPL").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows diagonal correlation value 1.00 three times for 3x3 matrix", async () => {
    render(<CorrelationMatrixPanel />);
    await waitFor(() => {
      const cells = screen.getAllByText("1.00");
      expect(cells.length).toBe(3);
    });
  });
});

// ─── EconomicCalendarPanel ───────────────────────────────────────────────────
describe("EconomicCalendarPanel", () => {
  it("renders panel title ECONOMIC CALENDAR", async () => {
    await act(async () => { render(<EconomicCalendarPanel />); });
    expect(screen.getByText("ECONOMIC CALENDAR")).toBeInTheDocument();
  });

  it("renders HIGH, MEDIUM, LOW filter toggles", async () => {
    await act(async () => { render(<EconomicCalendarPanel />); });
    expect(screen.getByRole("button", { name: /^high$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^medium$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^low$/i })).toBeInTheDocument();
  });

  it("loads and displays FOMC Meeting event", async () => {
    render(<EconomicCalendarPanel />);
    // FOMC Meeting appears in both the next-event banner and grouped list
    await waitFor(() => {
      const matches = screen.getAllByText("FOMC Meeting");
      expect(matches.length).toBeGreaterThanOrEqual(1);
    }, { timeout: 3000 });
  });

  it("displays CPI Report event", async () => {
    render(<EconomicCalendarPanel />);
    await waitFor(() => {
      expect(screen.getByText("CPI Report")).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it("shows next high-impact event countdown as 2D", async () => {
    render(<EconomicCalendarPanel />);
    // next high-impact banner shows "${daysUntilNext}D" for days > 1
    await waitFor(() => {
      expect(screen.getByText("2D")).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it("hides medium events when medium filter toggled off", async () => {
    render(<EconomicCalendarPanel />);
    await waitFor(() => screen.getByText("Retail Sales"), { timeout: 3000 });
    fireEvent.click(screen.getByRole("button", { name: /^medium$/i }));
    await waitFor(() => {
      expect(screen.queryByText("Retail Sales")).not.toBeInTheDocument();
    });
  });
});

// ─── DarkPoolPanel ────────────────────────────────────────────────────────────
describe("DarkPoolPanel", () => {
  it("renders panel title UNUSUAL OPTIONS ACTIVITY", async () => {
    await act(async () => { render(<DarkPoolPanel />); });
    expect(screen.getByText("UNUSUAL OPTIONS ACTIVITY")).toBeInTheDocument();
  });

  it("displays NVDA and SPY activity rows", async () => {
    render(<DarkPoolPanel />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    expect(screen.getByText("SPY")).toBeInTheDocument();
  });

  it("renders symbol filter input", async () => {
    await act(async () => { render(<DarkPoolPanel />); });
    expect(screen.getByRole("textbox", { name: /filter symbol/i })).toBeInTheDocument();
  });

  it("renders sort-by combobox with PREMIUM option", async () => {
    await act(async () => { render(<DarkPoolPanel />); });
    const sortSelect = screen.getByRole("combobox", { name: /sort by/i });
    expect(sortSelect).toBeInTheDocument();
    expect(sortSelect).toHaveValue("premium");
  });

  it("shows CALL contract type label", async () => {
    render(<DarkPoolPanel />);
    await waitFor(() => {
      const calls = screen.getAllByText(/call/i);
      expect(calls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows PUT contract type label", async () => {
    render(<DarkPoolPanel />);
    await waitFor(() => {
      const puts = screen.getAllByText(/put/i);
      expect(puts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows FLOW BIAS indicator", async () => {
    render(<DarkPoolPanel />);
    await waitFor(() => {
      expect(screen.getByText("FLOW BIAS")).toBeInTheDocument();
    });
  });
});

// ─── CryptoPanel ──────────────────────────────────────────────────────────────
describe("CryptoPanel", () => {
  it("renders panel title CRYPTO", async () => {
    await act(async () => { render(<CryptoPanel />); });
    expect(screen.getByText("CRYPTO")).toBeInTheDocument();
  });

  it("shows FUNDING, MOVERS, ONCHAIN tab buttons", async () => {
    await act(async () => { render(<CryptoPanel />); });
    expect(screen.getByRole("button", { name: /funding/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /movers/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /onchain/i })).toBeInTheDocument();
  });

  it("displays BTC funding rate on default tab", async () => {
    render(<CryptoPanel />);
    await waitFor(() => {
      expect(screen.getByText("BTC")).toBeInTheDocument();
    });
  });

  it("shows PERPETUAL FUNDING RATES section header", async () => {
    render(<CryptoPanel />);
    await waitFor(() => {
      expect(screen.getByText(/perpetual funding rates/i)).toBeInTheDocument();
    });
  });

  it("switches to MOVERS tab and shows TOP GAINERS / TOP LOSERS", async () => {
    render(<CryptoPanel />);
    await waitFor(() => screen.getByText(/perpetual funding rates/i));
    fireEvent.click(screen.getByRole("button", { name: /movers/i }));
    await waitFor(() => {
      expect(screen.getByText(/top gainers/i)).toBeInTheDocument();
      expect(screen.getByText(/top losers/i)).toBeInTheDocument();
    });
  });

  it("switches to ONCHAIN tab and shows BTC ON-CHAIN section", async () => {
    render(<CryptoPanel />);
    await waitFor(() => screen.getByText(/perpetual funding rates/i));
    fireEvent.click(screen.getByRole("button", { name: /onchain/i }));
    await waitFor(() => {
      expect(screen.getByText(/btc on-chain/i)).toBeInTheDocument();
    });
  });

  it("shows ETH funding rate on default tab", async () => {
    render(<CryptoPanel />);
    await waitFor(() => {
      expect(screen.getByText("ETH")).toBeInTheDocument();
    });
  });
});
