# frontend/components — Reusable UI Building Blocks

## What is this folder?

Components are the LEGO bricks of the user interface. Each component is a self-contained piece of the UI — a button, a panel, a chart — that can be placed anywhere on the page and reused across different screens.

Think of it like furniture: you don't redesign a chair every time you need one. You build it once, and place it wherever needed.

---

## Subfolders

```
components/
├── panels/     The 23 major dashboard panels (chart, watchlist, etc.)
├── layout/     The structural chrome: header, sidebar, panel grid, ticker tape
├── providers/  React context providers (theme, query client, auth guard)
└── ui/         Small, generic UI primitives (currently: Sparkline mini-chart)
```

---

## `layout/` — The Dashboard Shell

These components form the skeleton that all panels sit inside:

**`Header.tsx`** — The top navigation bar. Shows the platform name, a global symbol search, the user's account menu, and the Grafana/settings links.

**`Sidebar.tsx`** — The left-side navigation panel. Contains links to toggle different panels on/off, workspace switching, and the panel visibility controls.

**`TickerTape.tsx`** — The scrolling strip at the very top of the page showing live prices for all watchlist symbols. Updates in real time as WebSocket messages arrive.

**`Panel.tsx`** — A wrapper component that every single dashboard panel is wrapped in. It adds the panel's title bar, resize handles, and a collapse/expand button. Think of it like a picture frame — each panel picture goes inside a standard frame.

**`PanelGrid.tsx`** — Uses `react-grid-layout` to arrange all visible panels in a drag-and-drop grid. Reads layout positions from the `layoutStore` and writes back when the user rearranges panels. The grid is 12 columns wide; panel widths/heights are measured in grid units.

---

## `panels/` — The 23 Dashboard Panels

See [`panels/README.md`](panels/README.md) for a full description of each panel.

Quick list:
`ChartPanel` · `WatchlistPanel` · `PortfolioPanel` · `NewsFeedPanel` · `OrderBookPanel` · `TimeAndSalesPanel` · `RiskPanel` · `OptionsChainPanel` · `ScreenerPanel` · `AlertsPanel` · `MacroPanel` · `EconomicCalendarPanel` · `HeatMapPanel` · `CorrelationMatrixPanel` · `DarkPoolPanel` · `CryptoPanel` · `PerformancePanel` · `MultiTimeframePanel` · `OrderEntryPanel` · `BacktestPanel` · `VolatilityPanel` · `TradeJournalPanel` · `StrategyBuilderPanel`

---

## `ui/` — Generic Primitives

**`Sparkline.tsx`** — A tiny inline price chart (just a line, no axes). Used inside the WatchlistPanel and TickerTape to show price direction at a glance. Takes an array of numbers and draws a scaled SVG polyline.

---

## `providers/` — Context Wrappers

React "providers" wrap the entire app and make certain things available everywhere without passing them as props. Examples: the React Query client (for server-state caching), the theme provider, and the authentication guard that checks if the user is logged in before rendering any protected page content.

---

## How does this connect to the rest of the app?

- Panels read live data from `store/marketDataStore` (prices) and `store/layoutStore` (panel positions)
- Panels call backend endpoints via functions in `lib/api/`
- The `PanelGrid` in `layout/` renders whatever panels the `layoutStore` says are visible
- All panels are rendered inside the `Panel` wrapper from `layout/Panel.tsx` for consistent styling
