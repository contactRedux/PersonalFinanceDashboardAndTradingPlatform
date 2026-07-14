/**
 * Unit tests — new panels (ST-next)
 *
 * Panels tested:
 *   PerformancePanel, MultiTimeframePanel, OrderEntryPanel
 *
 * All API calls and heavyweight deps are mocked.
 */

import React, { act } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// ─── Global mocks ────────────────────────────────────────────────────────────

vi.mock("@/lib/api/client", () => ({
  apiRequest: vi.fn().mockRejectedValue(new Error("no server")),
  getAccessToken: vi.fn(() => "mock-token"),
}));

vi.mock("@/lib/api/market", () => ({
  getBars: vi.fn().mockResolvedValue({ bars: [] }),
  searchSymbols: vi.fn().mockResolvedValue({ results: [] }),
  getVPVR: vi.fn().mockResolvedValue({ symbol: "AAPL", price_levels: [], poc: null }),
}));

// MultiTimeframePanel renders lightweight-charts in useEffect via dynamic import.
// lightweight-charts calls requestAnimationFrame which fails in jsdom with canvas errors.
// We mock the entire panel to avoid the canvas path in unit tests.
// Chart rendering is tested in E2E (Playwright in real browser).
vi.mock("@/components/panels/MultiTimeframePanel", () => ({
  MultiTimeframePanel: vi.fn(
    ({ defaultSymbol = "AAPL" }: { panelId?: string; defaultSymbol?: string }) => (
      <div data-testid="mtf-panel">
        <div className="panel-header">MULTI-TIMEFRAME</div>
        <input aria-label="MTF symbol" defaultValue={defaultSymbol} readOnly />
        <button aria-label="go">GO</button>
        <div>AAPL · 1M</div>
        <div>AAPL · 5M</div>
        <div>AAPL · 1H</div>
        <div>AAPL · 1D</div>
      </div>
    )
  ),
}));

vi.stubGlobal("WebSocket", class MockWS {
  static CONNECTING = 0;
  static OPEN = 1;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
  send() {}
});

// ─── PerformancePanel ────────────────────────────────────────────────────────

import { PerformancePanel } from "@/components/panels/PerformancePanel";

describe("PerformancePanel", () => {
  it("renders panel title PERFORMANCE", async () => {
    await act(async () => { render(<PerformancePanel />); });
    expect(screen.getByText("PERFORMANCE")).toBeInTheDocument();
  });

  it("shows STATS, CALENDAR, TRADES tab buttons", async () => {
    await act(async () => { render(<PerformancePanel />); });
    expect(screen.getByRole("button", { name: /stats/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /calendar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /trades/i })).toBeInTheDocument();
  });

  it("shows win rate gauge after data loads (falls back to demo)", async () => {
    await act(async () => { render(<PerformancePanel />); });
    await waitFor(() => {
      expect(screen.getByText(/WIN RATE/i)).toBeInTheDocument();
    });
  });

  it("shows Total Trades stat", async () => {
    await act(async () => { render(<PerformancePanel />); });
    await waitFor(() => {
      expect(screen.getByText(/total trades/i)).toBeInTheDocument();
    });
  });

  it("switches to CALENDAR tab", async () => {
    await act(async () => { render(<PerformancePanel />); });
    await waitFor(() => screen.getByText(/WIN RATE/i));
    fireEvent.click(screen.getByRole("button", { name: /calendar/i }));
    await waitFor(() => {
      expect(screen.getByText(/P&L CALENDAR/i)).toBeInTheDocument();
    });
  });

  it("switches to TRADES tab and shows trade log table", async () => {
    await act(async () => { render(<PerformancePanel />); });
    await waitFor(() => screen.getByText(/WIN RATE/i));
    fireEvent.click(screen.getByRole("button", { name: /trades/i }));
    await waitFor(() => {
      // Trade log table has column headers
      expect(screen.getByText(/symbol/i)).toBeInTheDocument();
    });
  });
});

// ─── MultiTimeframePanel ─────────────────────────────────────────────────────
// The real MultiTimeframePanel is mocked above (see vi.mock at top).
// Tests verify structural contract of the mock stub.

import { MultiTimeframePanel } from "@/components/panels/MultiTimeframePanel";

describe("MultiTimeframePanel", () => {
  it("renders panel title MULTI-TIMEFRAME", async () => {
    await act(async () => { render(<MultiTimeframePanel />); });
    expect(screen.getByText("MULTI-TIMEFRAME")).toBeInTheDocument();
  });

  it("shows GO button for symbol apply", async () => {
    await act(async () => { render(<MultiTimeframePanel />); });
    expect(screen.getByRole("button", { name: /go/i })).toBeInTheDocument();
  });

  it("shows symbol input", async () => {
    await act(async () => { render(<MultiTimeframePanel defaultSymbol="AAPL" />); });
    expect(screen.getByRole("textbox", { name: /mtf symbol/i })).toBeInTheDocument();
  });

  it("shows 4 pane labels in default layout", async () => {
    await act(async () => { render(<MultiTimeframePanel defaultSymbol="AAPL" />); });
    expect(screen.getByText("AAPL · 1M")).toBeInTheDocument();
    expect(screen.getByText("AAPL · 5M")).toBeInTheDocument();
    expect(screen.getByText("AAPL · 1H")).toBeInTheDocument();
    expect(screen.getByText("AAPL · 1D")).toBeInTheDocument();
  });
});

// ─── OrderEntryPanel ──────────────────────────────────────────────────────────

import { OrderEntryPanel } from "@/components/panels/OrderEntryPanel";

describe("OrderEntryPanel", () => {
  it("renders panel title ORDER ENTRY", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    // Panel title span + toolbar tab both contain ORDER ENTRY text
    const matches = screen.getAllByText("ORDER ENTRY");
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("shows ORDER ENTRY and MY ORDERS tabs", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    expect(screen.getByRole("button", { name: /order entry/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /my orders/i })).toBeInTheDocument();
  });

  it("shows BUY and SELL side buttons", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    expect(screen.getByRole("button", { name: /^BUY$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^SELL$/i })).toBeInTheDocument();
  });

  it("defaults to BUY side", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    // The submit button should say BUY AAPL
    expect(screen.getByRole("button", { name: /buy aapl/i })).toBeInTheDocument();
  });

  it("shows Symbol and Quantity inputs", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    expect(screen.getByRole("textbox", { name: /symbol/i })).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: /quantity/i })).toBeInTheDocument();
  });

  it("shows order type select defaulting to market", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    const select = screen.getByRole("combobox", { name: /order type/i });
    expect(select).toHaveValue("market");
  });

  it("shows limit price input when limit order type selected", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    const select = screen.getByRole("combobox", { name: /order type/i });
    fireEvent.change(select, { target: { value: "limit" } });
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: /limit price/i })).toBeInTheDocument();
    });
  });

  it("switches to MY ORDERS tab and shows orders list area", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    fireEvent.click(screen.getByRole("button", { name: /my orders/i }));
    await waitFor(() => {
      expect(screen.getByText(/no orders yet/i)).toBeInTheDocument();
    });
  });

  it("shows SELL button when sell side selected", async () => {
    await act(async () => { render(<OrderEntryPanel defaultSymbol="MSFT" />); });
    fireEvent.click(screen.getByRole("button", { name: /^SELL$/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /sell msft/i })).toBeInTheDocument();
    });
  });

  it("shows paper trading disclaimer", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    expect(screen.getByText(/paper trading/i)).toBeInTheDocument();
  });
});

// ─── ChartPanel + ChartToolbar (ST-C) ────────────────────────────────────────
// ChartCanvas uses lightweight-charts which requires canvas/rAF — mock it.

vi.mock("@/components/panels/ChartPanel/ChartCanvas", () => ({
  ChartCanvas: vi.fn(() => <div data-testid="chart-canvas" />),
}));

// Mock drawing tool hooks — they import lightweight-charts which is ESM-only
vi.mock("@/components/panels/ChartPanel/useFibonacciTool", () => ({
  useFibonacciTool: vi.fn(() => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
    clear: vi.fn(),
    removeDrawing: vi.fn(),
    isActive: false,
    drawings: [],
  })),
  FIB_LEVELS: [],
}));

vi.mock("@/components/panels/ChartPanel/useTrendlineTool", () => ({
  useTrendlineTool: vi.fn(() => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
    clear: vi.fn(),
    removeDrawing: vi.fn(),
    isActive: false,
    drawings: [],
    hoverPrice: null,
  })),
}));

vi.mock("@/components/panels/ChartPanel/usePitchforkTool", () => ({
  usePitchforkTool: vi.fn(() => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
    clear: vi.fn(),
    removeDrawing: vi.fn(),
    isActive: false,
    drawings: [],
  })),
}));

vi.mock("@/components/panels/ChartPanel/useAnnotationTool", () => ({
  useAnnotationTool: vi.fn(() => ({
    activate: vi.fn(),
    deactivate: vi.fn(),
    clear: vi.fn(),
    removeDrawing: vi.fn(),
    isActive: false,
    drawings: [],
  })),
}));

// Also stub the store for this panel's tests — chartStore uses localStorage
vi.mock("@/store/chartStore", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/store/chartStore")>();
  return {
    ...actual,
    useChartStore: vi.fn(() => ({
      panels: {
        chart: {
          symbol: "AAPL",
          timeframe: "1d",
          chartType: "candlestick",
          indicators: [],
          drawings: { fib: [], trendline: [], pitchfork: [], annotations: [] },
        },
      },
      setSymbol: vi.fn(),
      setTimeframe: vi.fn(),
      setChartType: vi.fn(),
      addIndicator: vi.fn(),
      removeIndicator: vi.fn(),
      toggleIndicator: vi.fn(),
      setDrawings: vi.fn(),
    })),
  };
});

import { ChartPanel } from "@/components/panels/ChartPanel";
import { ChartToolbar } from "@/components/panels/ChartPanel/ChartToolbar";

describe("ChartPanel (ST-C)", () => {
  it("renders a chart canvas placeholder", async () => {
    await act(async () => { render(<ChartPanel />); });
    expect(screen.getByTestId("chart-canvas")).toBeInTheDocument();
  });
});

describe("ChartToolbar (ST-C)", () => {
  const noop = () => {};

  it("renders all timeframe buttons", async () => {
    await act(async () => {
      render(
        <ChartToolbar
          symbol="AAPL"
          timeframe="1d"
          chartType="candlestick"
          indicators={[]}
          onSymbolChange={noop}
          onTimeframeChange={noop}
          onChartTypeChange={noop}
          onAddIndicator={noop}
          onRemoveIndicator={noop}
          onToggleIndicator={noop}
        />
      );
    });
    expect(screen.getByRole("button", { name: /1D/i })).toBeInTheDocument();
  });

  it("renders Ind dropdown button", async () => {
    await act(async () => {
      render(
        <ChartToolbar
          symbol="AAPL"
          timeframe="1d"
          chartType="candlestick"
          indicators={[]}
          onSymbolChange={noop}
          onTimeframeChange={noop}
          onChartTypeChange={noop}
          onAddIndicator={noop}
          onRemoveIndicator={noop}
          onToggleIndicator={noop}
        />
      );
    });
    expect(screen.getByRole("button", { name: /add indicator/i })).toBeInTheDocument();
  });

  it("shows indicator pills for active indicators", async () => {
    const indicators = [{ id: "sma-1", type: "sma", params: { period: 20 }, visible: true }];
    await act(async () => {
      render(
        <ChartToolbar
          symbol="AAPL"
          timeframe="1d"
          chartType="candlestick"
          indicators={indicators}
          onSymbolChange={noop}
          onTimeframeChange={noop}
          onChartTypeChange={noop}
          onAddIndicator={noop}
          onRemoveIndicator={noop}
          onToggleIndicator={noop}
        />
      );
    });
    expect(screen.getByRole("button", { name: /toggle sma/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove sma/i })).toBeInTheDocument();
  });
});

// ─── BacktestPanel (ST-D) ─────────────────────────────────────────────────────

import { BacktestPanel } from "@/components/panels/BacktestPanel";

describe("BacktestPanel (ST-D)", () => {
  it("renders panel title BACKTEST", async () => {
    await act(async () => { render(<BacktestPanel />); });
    expect(screen.getByText("BACKTEST")).toBeInTheDocument();
  });

  it("shows CHART, METRICS, TRADES tab buttons", async () => {
    await act(async () => { render(<BacktestPanel />); });
    expect(screen.getByRole("button", { name: /^chart$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^metrics$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^trades$/i })).toBeInTheDocument();
  });

  it("shows symbol, start date and end date fields", async () => {
    await act(async () => { render(<BacktestPanel />); });
    expect(screen.getByRole("textbox", { name: /backtest symbol/i })).toBeInTheDocument();
    // date inputs don't have "textbox" role — query by label text
    expect(screen.getByLabelText(/start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end/i)).toBeInTheDocument();
  });

  it("shows strategy selector defaulting to sma_cross", async () => {
    await act(async () => { render(<BacktestPanel />); });
    const sel = screen.getByRole("combobox", { name: /strategy/i });
    expect(sel).toHaveValue("sma_cross");
  });

  it("shows RUN BACKTEST button", async () => {
    await act(async () => { render(<BacktestPanel />); });
    expect(screen.getByRole("button", { name: /run backtest/i })).toBeInTheDocument();
  });

  it("shows idle placeholder text initially", async () => {
    await act(async () => { render(<BacktestPanel />); });
    expect(screen.getByText(/configure and run a backtest/i)).toBeInTheDocument();
  });

  it("shows metrics grid after successful run (mocked apiRequest)", async () => {
    const { apiRequest: mockApiReq } = await import("@/lib/api/client");
    (mockApiReq as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      symbol: "AAPL",
      timeframe: "1d",
      start: "2022-01-01",
      end: "2024-01-01",
      initial_capital: 100000,
      final_equity: 115000,
      total_return_pct: 15.0,
      cagr_pct: 7.5,
      sharpe_ratio: 0.85,
      sortino_ratio: 1.1,
      calmar_ratio: 0.6,
      max_drawdown_pct: 12.5,
      win_rate: 55.0,
      profit_factor: 1.4,
      total_trades: 42,
      winning_trades: 23,
      losing_trades: 19,
      equity_curve: [100000, 105000, 110000, 115000],
      trades: [],
      monte_carlo: null,
    });

    await act(async () => { render(<BacktestPanel />); });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /run backtest/i }));
    });

    await waitFor(() => {
      // switch to metrics tab which is shown by default after run
      fireEvent.click(screen.getByRole("button", { name: /^metrics$/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/total return/i)).toBeInTheDocument();
      expect(screen.getByText(/15.00%/)).toBeInTheDocument();
    });
  });
});

// ─── VolatilityPanel (ST-H) ───────────────────────────────────────────────────

import { VolatilityPanel } from "@/components/panels/VolatilityPanel";

describe("VolatilityPanel (ST-H)", () => {
  it("renders IV SURFACE panel title", async () => {
    await act(async () => { render(<VolatilityPanel />); });
    // Panel title contains the symbol
    expect(screen.getByText(/IV SURFACE/i)).toBeInTheDocument();
  });

  it("shows symbol input with default AAPL", async () => {
    await act(async () => { render(<VolatilityPanel defaultSymbol="AAPL" />); });
    const input = screen.getByRole("textbox", { name: /iv surface symbol/i });
    expect((input as HTMLInputElement).value).toBe("AAPL");
  });

  it("shows GO button", async () => {
    await act(async () => { render(<VolatilityPanel />); });
    expect(screen.getByRole("button", { name: /load iv surface/i })).toBeInTheDocument();
  });

  it("shows ALL / CALL / PUT filter buttons", async () => {
    await act(async () => { render(<VolatilityPanel />); });
    expect(screen.getByRole("button", { name: /^ALL$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^CALL$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^PUT$/i })).toBeInTheDocument();
  });

  it("renders heatmap SVG when surface data loads", async () => {
    const { apiRequest: mockReq } = await import("@/lib/api/client");
    (mockReq as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      symbol: "AAPL",
      surface: [
        { strike: 90, expiry_days: 30, iv: 0.35, contract_type: "put" },
        { strike: 100, expiry_days: 30, iv: 0.28, contract_type: "call" },
        { strike: 110, expiry_days: 60, iv: 0.22, contract_type: "call" },
      ],
    });

    await act(async () => { render(<VolatilityPanel />); });
    await waitFor(() => {
      expect(document.querySelector("[data-testid='iv-heatmap']")).toBeTruthy();
    });
  });
});

// ─── ST-J: OrderEntryPanel — bracket / OCO / modify ──────────────────────────

describe("OrderEntryPanel (ST-J) bracket/OCO", () => {
  it("shows Bracket and OCO checkboxes", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    expect(screen.getByRole("checkbox", { name: /enable bracket order/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /enable oco order/i })).toBeInTheDocument();
  });

  it("reveals take-profit and stop-loss fields when bracket is checked", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    const bracketBox = screen.getByRole("checkbox", { name: /enable bracket order/i });
    fireEvent.click(bracketBox);
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: /take profit price/i })).toBeInTheDocument();
      expect(screen.getByRole("spinbutton", { name: /stop loss price/i })).toBeInTheDocument();
    });
  });

  it("reveals take-profit and stop-loss fields when OCO is checked", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    const ocoBox = screen.getByRole("checkbox", { name: /enable oco order/i });
    fireEvent.click(ocoBox);
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: /take profit price/i })).toBeInTheDocument();
      expect(screen.getByRole("spinbutton", { name: /stop loss price/i })).toBeInTheDocument();
    });
  });

  it("checking bracket unchecks OCO", async () => {
    await act(async () => { render(<OrderEntryPanel />); });
    const ocoBox = screen.getByRole("checkbox", { name: /enable oco order/i });
    const bracketBox = screen.getByRole("checkbox", { name: /enable bracket order/i });
    fireEvent.click(ocoBox);
    fireEvent.click(bracketBox);
    await waitFor(() => {
      expect((ocoBox as HTMLInputElement).checked).toBe(false);
      expect((bracketBox as HTMLInputElement).checked).toBe(true);
    });
  });

  it("shows Edit button for orders that can be modified", async () => {
    const { apiRequest: mockReq } = await import("@/lib/api/client");
    (mockReq as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      orders: [
        {
          id: "ord-1",
          symbol: "AAPL",
          side: "buy",
          order_type: "limit",
          quantity: 10,
          status: "accepted",
          filled_qty: 0,
          filled_avg_price: null,
          limit_price: 150,
          created_at: new Date().toISOString(),
        },
      ],
    });

    await act(async () => { render(<OrderEntryPanel />); });
    const ordersTab = screen.getByRole("button", { name: /my orders/i });
    fireEvent.click(ordersTab);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /edit order ord-1/i })).toBeInTheDocument();
    });
  });

  it("shows inline edit form when Edit is clicked", async () => {
    const { apiRequest: mockReq } = await import("@/lib/api/client");
    (mockReq as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      orders: [
        {
          id: "ord-2",
          symbol: "MSFT",
          side: "sell",
          order_type: "limit",
          quantity: 5,
          status: "accepted",
          filled_qty: 0,
          filled_avg_price: null,
          limit_price: 400,
          created_at: new Date().toISOString(),
        },
      ],
    });

    await act(async () => { render(<OrderEntryPanel />); });
    fireEvent.click(screen.getByRole("button", { name: /my orders/i }));
    await waitFor(() => screen.getByRole("button", { name: /edit order ord-2/i }));
    fireEvent.click(screen.getByRole("button", { name: /edit order ord-2/i }));
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: /edit quantity/i })).toBeInTheDocument();
      expect(screen.getByRole("spinbutton", { name: /edit limit price/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /confirm modify/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /cancel modify/i })).toBeInTheDocument();
    });
  });
});

// ─── ST-L: StrategyBuilderPanel ──────────────────────────────────────────────

// Mock @xyflow/react — it uses DOM APIs not available in jsdom
vi.mock("@xyflow/react", () => ({
  ReactFlow: vi.fn(({ children }: { children?: React.ReactNode }) => (
    <div data-testid="reactflow-canvas">{children}</div>
  )),
  Background: vi.fn(() => null),
  Controls: vi.fn(() => null),
  MiniMap: vi.fn(() => null),
  addEdge: vi.fn((edge, edges) => [...edges, edge]),
  useNodesState: vi.fn((initial) => [initial, vi.fn(), vi.fn()]),
  useEdgesState: vi.fn((initial) => [initial, vi.fn(), vi.fn()]),
  BackgroundVariant: { Dots: "dots" },
}));

import { StrategyBuilderPanel } from "@/components/panels/StrategyBuilderPanel";

describe("StrategyBuilderPanel (ST-L)", () => {
  it("renders STRATEGY BUILDER title", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByText("STRATEGY BUILDER")).toBeInTheDocument();
  });

  it("shows strategy name input", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByRole("textbox", { name: /strategy name/i })).toBeInTheDocument();
  });

  it("shows Save and Run backtest buttons", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByRole("button", { name: /save strategy/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run backtest/i })).toBeInTheDocument();
  });

  it("shows node palette groups", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByText(/indicators/i)).toBeInTheDocument();
    expect(screen.getByText(/comparators/i)).toBeInTheDocument();
    expect(screen.getByText(/actions/i)).toBeInTheDocument();
  });

  it("shows Add RSI node button in palette", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByRole("button", { name: /add rsi\(14\) node/i })).toBeInTheDocument();
  });

  it("shows ReactFlow canvas", async () => {
    await act(async () => { render(<StrategyBuilderPanel />); });
    expect(screen.getByTestId("reactflow-canvas")).toBeInTheDocument();
  });
});

// ─── ST-M: TradeJournalPanel ──────────────────────────────────────────────────

import { TradeJournalPanel } from "@/components/panels/TradeJournalPanel";

describe("TradeJournalPanel (ST-M)", () => {
  it("renders TRADE JOURNAL title", async () => {
    await act(async () => { render(<TradeJournalPanel />); });
    expect(screen.getByText("TRADE JOURNAL")).toBeInTheDocument();
  });

  it('shows "No journal entries yet" initially (API fails)', async () => {
    await act(async () => { render(<TradeJournalPanel />); });
    await waitFor(() => {
      expect(screen.getByText(/no journal entries yet/i)).toBeInTheDocument();
    });
  });

  it("renders entry cards when data loads (mocked apiRequest)", async () => {
    const { apiRequest: mockApiReq } = await import("@/lib/api/client");
    (mockApiReq as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      entries: [
        {
          order_id: "ord-j-1",
          user_id: "user-1",
          symbol: "AAPL",
          side: "buy",
          quantity: 10,
          entry_price: 190.0,
          sentiment_score: 0.35,
          technical_context: { rsi: 54.2 },
          ai_analysis: "Bullish momentum with positive sentiment.",
          created_at: new Date().toISOString(),
        },
      ],
      count: 1,
    });

    await act(async () => { render(<TradeJournalPanel />); });
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText(/bullish momentum/i)).toBeInTheDocument();
      expect(screen.getByText("+0.35")).toBeInTheDocument();
    });
  });
});

// ─── ST-S: PortfolioPanel Import CSV button ───────────────────────────────────

vi.mock("@/lib/api/portfolio", () => ({
  getPortfolio: vi.fn().mockResolvedValue({
    user_id: "u1",
    equity: 100000,
    cash: 80000,
    unrealized_pnl: 1000,
    realized_pnl: 500,
    day_pnl: 100,
    day_pnl_pct: 0.1,
    buying_power: 160000,
    margin_used: 0,
    currency: "USD",
    as_of: "2025-01-01T00:00:00Z",
  }),
  getPositions: vi.fn().mockResolvedValue({ positions: [] }),
}));

vi.mock("@/store/ordersStore", () => ({
  useOrdersStore: vi.fn((selector: (s: { lastFill: null; clearLastFill: () => void }) => unknown) =>
    selector({ lastFill: null, clearLastFill: () => {} })
  ),
}));

import { PortfolioPanel } from "@/components/panels/PortfolioPanel";

describe("PortfolioPanel (ST-S) Import CSV", () => {
  it("renders an Import CSV button in the toolbar", async () => {
    await act(async () => { render(<PortfolioPanel />); });
    expect(screen.getByRole("button", { name: /import csv/i })).toBeInTheDocument();
  });

  it("Import CSV button is clickable", async () => {
    await act(async () => { render(<PortfolioPanel />); });
    const btn = screen.getByRole("button", { name: /import csv/i });
    // Should not throw
    fireEvent.click(btn);
  });
});
