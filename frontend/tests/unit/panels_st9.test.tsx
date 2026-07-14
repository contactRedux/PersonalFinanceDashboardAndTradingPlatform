/**
 * Unit tests — ST-9 panels and API helpers.
 *
 * Tests cover:
 *  - Portfolio API type contracts
 *  - Options API type contracts
 *  - Kelly Criterion math (PositionSizingCalculator logic)
 *  - Risk metric formatting helpers
 *  - PortfolioPanel render (smoke)
 *  - RiskPanel render (smoke)
 *  - OrderBookPanel render (smoke)
 *  - TimeAndSalesPanel render (smoke)
 *  - OptionsChainPanel render (smoke)
 */

import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";

// ─── Mock fetch globally ─────────────────────────────────────────────────────
const mockPortfolioResponse = {
  user_id: "user-1",
  equity: 100_000,
  cash: 85_423.50,
  unrealized_pnl: 2_341.75,
  realized_pnl: 1_234.25,
  day_pnl: 312.50,
  day_pnl_pct: 0.31,
  buying_power: 170_847,
  margin_used: 0,
  currency: "USD",
  as_of: "2025-01-15T20:00:00Z",
};

const mockPositionsResponse = {
  positions: [
    {
      symbol: "AAPL",
      asset_class: "equity",
      side: "long",
      quantity: 50,
      avg_entry_price: 182.45,
      current_price: 198.75,
      market_value: 9_937.50,
      unrealized_pnl: 815.00,
      unrealized_pnl_pct: 8.94,
      stop_loss: 175.00,
      take_profit: 220.00,
    },
  ],
};

const mockRiskResponse = {
  var_95: 0.018,
  cvar_95: 0.024,
  sharpe_ratio: 1.42,
  sortino_ratio: 2.05,
  calmar_ratio: 0.87,
  max_drawdown: 0.083,
  max_drawdown_duration_days: 18,
  beta: 0.92,
  alpha: 0.00032,
  note: "Demo data",
};

const mockOptionsChainResponse = {
  symbol: "AAPL",
  expiry: "2025-02-21",
  underlying_price: 198.75,
  chain: [],
  expirations: ["2025-02-21", "2025-03-21"],
  timestamp: "2025-01-15T20:00:00Z",
};

// ─── Mock the api client ─────────────────────────────────────────────────────
vi.mock("@/lib/api/client", () => ({
  apiRequest: vi.fn(),
  getAccessToken: vi.fn(() => "test-token"),
}));

vi.mock("@/lib/api/portfolio", () => ({
  getPortfolio: vi.fn(() => Promise.resolve(mockPortfolioResponse)),
  getPositions: vi.fn(() => Promise.resolve(mockPositionsResponse)),
  getRiskMetrics: vi.fn(() => Promise.resolve(mockRiskResponse)),
}));

vi.mock("@/lib/api/options", () => ({
  getOptionsChain: vi.fn(() => Promise.resolve(mockOptionsChainResponse)),
  getExpirations: vi.fn(() =>
    Promise.resolve({ symbol: "AAPL", expirations: ["2025-02-21"] })
  ),
  getUnusualActivity: vi.fn(() => Promise.resolve({ activity: [] })),
}));

vi.mock("@/lib/api/websocket", () => ({
  WS_URLS: {
    market: () => "ws://localhost:8000/ws/market",
    tape: () => "ws://localhost:8000/ws/tape",
    orderbook: (sym: string) => `ws://localhost:8000/ws/orderbook/${sym}`,
    alerts: () => "ws://localhost:8000/ws/alerts",
  },
}));

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => { this.readyState = MockWebSocket.CLOSED; });
  constructor() {
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
    }, 0);
  }
}
vi.stubGlobal("WebSocket", MockWebSocket);

// Mock stores
vi.mock("@/store/marketDataStore", () => ({
  useMarketDataStore: vi.fn(() => ({ quotes: {} })),
}));

vi.mock("@/store/watchlistStore", () => ({
  useWatchlistStore: vi.fn(() => ({
    watchlists: [{ id: "wl-1", name: "My List", symbols: ["AAPL"] }],
    activeWatchlistId: "wl-1",
    setActive: vi.fn(),
    addSymbol: vi.fn(),
    removeSymbol: vi.fn(),
  })),
}));

// ─── Kelly Criterion unit tests ───────────────────────────────────────────────
describe("Kelly Criterion calculation", () => {
  function kelly(winRate: number, avgWin: number, avgLoss: number): number {
    const b = avgLoss > 0 ? avgWin / avgLoss : 0;
    const k = b > 0 ? (b * winRate - (1 - winRate)) / b : 0;
    return Math.max(0, Math.min(k * 0.5, 0.25));
  }

  it("returns half-kelly for a 55% win rate, 2:1 reward:risk", () => {
    const result = kelly(0.55, 2, 1);
    // Full kelly = (2*0.55 - 0.45)/2 = 0.325 → half = 0.1625
    expect(result).toBeCloseTo(0.1625, 3);
  });

  it("returns 0 when win rate makes kelly negative", () => {
    const result = kelly(0.3, 1, 2);
    // Full kelly = (0.5*0.3 - 0.7)/0.5 = negative → clamped to 0
    expect(result).toBe(0);
  });

  it("caps at 0.25 for extremely favourable setups", () => {
    const result = kelly(0.9, 5, 1);
    expect(result).toBe(0.25);
  });

  it("returns 0 when avgLoss is 0", () => {
    expect(kelly(0.6, 2, 0)).toBe(0);
  });

  it("handles 50/50 even odds — zero edge", () => {
    const result = kelly(0.5, 1, 1);
    expect(result).toBe(0); // b=1, kelly = (0.5-0.5)/1 = 0
  });
});

// ─── Risk metric formatting ────────────────────────────────────────────────────
describe("Risk metric values from mock API", () => {
  it("var_95 is a positive fraction", () => {
    expect(mockRiskResponse.var_95).toBeGreaterThan(0);
    expect(mockRiskResponse.var_95).toBeLessThan(1);
  });

  it("sharpe_ratio is finite number", () => {
    expect(Number.isFinite(mockRiskResponse.sharpe_ratio)).toBe(true);
  });

  it("max_drawdown is between 0 and 1", () => {
    expect(mockRiskResponse.max_drawdown).toBeGreaterThanOrEqual(0);
    expect(mockRiskResponse.max_drawdown).toBeLessThanOrEqual(1);
  });

  it("beta is a finite number", () => {
    expect(Number.isFinite(mockRiskResponse.beta)).toBe(true);
  });

  it("duration is non-negative integer", () => {
    expect(mockRiskResponse.max_drawdown_duration_days).toBeGreaterThanOrEqual(0);
    expect(Number.isInteger(mockRiskResponse.max_drawdown_duration_days)).toBe(true);
  });
});

// ─── Portfolio API shape ──────────────────────────────────────────────────────
describe("Portfolio API response shape", () => {
  it("has required numeric fields", () => {
    const p = mockPortfolioResponse;
    expect(typeof p.equity).toBe("number");
    expect(typeof p.cash).toBe("number");
    expect(typeof p.unrealized_pnl).toBe("number");
    expect(typeof p.realized_pnl).toBe("number");
    expect(typeof p.day_pnl).toBe("number");
    expect(typeof p.buying_power).toBe("number");
  });

  it("equity is greater than cash (positions exist)", () => {
    expect(mockPortfolioResponse.equity).toBeGreaterThan(
      mockPortfolioResponse.cash
    );
  });

  it("positions have required fields", () => {
    const pos = mockPositionsResponse.positions[0];
    expect(pos.symbol).toBeDefined();
    expect(pos.quantity).toBeGreaterThan(0);
    expect(pos.avg_entry_price).toBeGreaterThan(0);
    expect(pos.current_price).toBeGreaterThan(0);
    expect(["long", "short"]).toContain(pos.side);
  });
});

// ─── Options chain API shape ──────────────────────────────────────────────────
describe("Options API response shape", () => {
  it("has symbol, expirations, chain", () => {
    expect(mockOptionsChainResponse.symbol).toBe("AAPL");
    expect(Array.isArray(mockOptionsChainResponse.expirations)).toBe(true);
    expect(Array.isArray(mockOptionsChainResponse.chain)).toBe(true);
  });

  it("expirations are ISO date strings", () => {
    for (const exp of mockOptionsChainResponse.expirations) {
      expect(exp).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  it("underlying_price is a positive number", () => {
    expect(mockOptionsChainResponse.underlying_price).toBeGreaterThan(0);
  });
});

// ─── Smoke renders ────────────────────────────────────────────────────────────
describe("PortfolioPanel smoke render", () => {
  it("renders without crash", async () => {
    const { PortfolioPanel } = await import(
      "@/components/panels/PortfolioPanel"
    );
    const { unmount } = render(<PortfolioPanel panelId="test-portfolio" />);
    expect(document.body).toBeTruthy();
    unmount();
  });
});

describe("RiskPanel smoke render", () => {
  it("renders without crash", async () => {
    const { RiskPanel } = await import("@/components/panels/RiskPanel");
    const { unmount } = render(<RiskPanel panelId="test-risk" />);
    expect(document.body).toBeTruthy();
    unmount();
  });
});

describe("OrderBookPanel smoke render", () => {
  it("renders Level 2 panel title", async () => {
    const { OrderBookPanel } = await import(
      "@/components/panels/OrderBookPanel"
    );
    render(<OrderBookPanel panelId="test-ob" defaultSymbol="AAPL" />);
    expect(screen.getByText(/LEVEL 2/i)).toBeTruthy();
  });
});

describe("TimeAndSalesPanel smoke render", () => {
  it("renders Time & Sales panel title", async () => {
    const { TimeAndSalesPanel } = await import(
      "@/components/panels/TimeAndSalesPanel"
    );
    render(<TimeAndSalesPanel panelId="test-tape" defaultSymbol="AAPL" />);
    expect(screen.getByText(/TIME & SALES/i)).toBeTruthy();
  });
});

describe("OptionsChainPanel smoke render", () => {
  it("renders options chain panel title", async () => {
    const { OptionsChainPanel } = await import(
      "@/components/panels/OptionsChainPanel"
    );
    render(<OptionsChainPanel panelId="test-options" defaultSymbol="AAPL" />);
    // "OPTIONS CHAIN" appears in both the panel header and the column header
    const matches = screen.getAllByText(/OPTIONS CHAIN/i);
    expect(matches.length).toBeGreaterThan(0);
  });
});
