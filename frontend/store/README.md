# frontend/store — App State Management

## What is this folder?

State management is how a web app remembers things between interactions. For example: "which tickers is the user watching?" and "what is AAPL's current price?" need to be shared across many different panels simultaneously.

Think of the stores in this folder like a shared **whiteboard in an office**. Any team member (any panel) can read the whiteboard and write to it. When one person updates it, everyone else immediately sees the change.

QuantNexus uses **Zustand** — a lightweight state management library for React. Think of each store as a single topic on that whiteboard.

---

## The Stores

### `authStore.ts` — Who is logged in?

Stores the current user's identity and JWT tokens (a JSON Web Token is a small digitally-signed certificate that proves your identity — like a wristband at a concert that lets you back in if you step outside).

- **`user`** — the logged-in user's id, email, and role
- **`accessToken`** — short-lived token (15 minutes) sent with every API request
- **`refreshToken`** — longer-lived token (7 days) used to get a new access token when it expires
- **`setTokens(access, refresh)`** — called after a successful login; also sets a `qn-authed=1` cookie so the Edge Middleware can verify auth without reading localStorage
- **`clearAuth()`** — logs out, clears all tokens

Tokens are persisted to `localStorage` so you stay logged in after refreshing the page.

### `marketDataStore.ts` — Live Prices

Stores the latest price quote for every symbol the user has subscribed to.

- **`quotes`** — a dictionary mapping symbol → quote object (price, bid, ask, change_pct, etc.)
- **`priceHistory`** — stores the last 20 prices for each symbol (used to draw sparkline mini-charts)
- **`setQuote(quote)`** — called by `useMarketData` whenever a new price arrives via WebSocket; updates both `quotes` and appends to `priceHistory`
- **`getQuote(symbol)`** — returns the most recent quote for a symbol

### `layoutStore.ts` — Dashboard Layout

Controls which panels are visible and where they are positioned on the grid.

- **`layout`** — an array of position objects for each panel (x, y, width, height) in the 12-column grid format used by `react-grid-layout`
- **`panels`** — array of panel configs with `visible: true/false` and a display title
- **`setLayout(layout)`** — called when the user drags/resizes panels
- **`togglePanel(id)`** — shows/hides a specific panel
- **`resetLayout()`** — snaps everything back to the default arrangement

The layout is saved to `localStorage` so your arrangement persists between sessions. The default layout defines 23 panels with initial positions spread over a long scrollable page.

### `watchlistStore.ts` — Tracked Symbols

Manages the user's list of symbols to watch. Persists to the backend database (not just `localStorage`).

### `ordersStore.ts` — Last Order Fill

A minimal store tracking the most recently filled order, used to trigger notifications and portfolio refresh after a trade executes.

- **`lastFill`** — the most recent `OrderFill` object (symbol, side, quantity, fill price, time)
- **`setLastFill(fill)`** — called by the orders WebSocket feed when an order is filled
- **`clearLastFill()`** — resets after the notification has been shown

### `chartStore.ts` — Chart Settings

Stores the currently selected symbol for the main chart panel, active timeframe (1m, 5m, 1h, 1d...), and any overlay indicator configuration.

---

## How does this connect to the rest of the app?

- **Panels** read from stores using hooks like `useMarketDataStore((s) => s.getQuote("AAPL"))`
- **`useMarketData` hook** (`hooks/useMarketData.ts`) writes new prices to `marketDataStore` as WebSocket messages arrive
- **`useAuthStore`** is read by the `lib/api/client.ts` API client to get the access token to include in every request
- **`layoutStore`** is read by `components/layout/PanelGrid.tsx` to know what to render
- Zustand's `persist` middleware automatically syncs most stores to `localStorage`
