# frontend/ — The User Interface

## What is this folder?

This is everything the user sees and interacts with in their browser. When you open `http://localhost:3000`, you're loading the code from this folder.

The frontend is built with **Next.js 15** (a React framework — React being the most popular library for building interactive web interfaces) and **TypeScript** (JavaScript with type checking, which catches bugs before they happen).

Think of the backend as a restaurant kitchen, and the frontend as the dining room — this folder is the menus, the tables, the plates, and everything the customer actually touches.

---

## Key Files and Folders

| File / Folder | What it does |
|---|---|
| `app/` | Next.js App Router pages — the actual URLs you visit (e.g. `/login`, `/dashboard`) |
| `components/` | Reusable building blocks — buttons, panels, charts (see `components/README.md`) |
| `components/panels/` | The 23 dashboard panels (chart, watchlist, order book, etc.) |
| `store/` | Zustand stores — the app's shared memory between panels (see `store/README.md`) |
| `lib/` | Utility functions and API client functions (see `lib/README.md`) |
| `hooks/` | React hooks — reusable logic for WebSocket connections and auth state |
| `hooks/useWebSocket.ts` | Opens/manages a WebSocket connection with automatic reconnection |
| `hooks/useMarketData.ts` | Manages the single live price WebSocket connection shared by all panels |
| `hooks/useAuth.ts` | Login/logout state management |
| `types/` | TypeScript type definitions shared across the app |
| `public/` | Static assets: icons, images |
| `next.config.ts` | Next.js build configuration |
| `playwright.config.ts` | End-to-end test configuration |
| `package.json` | JavaScript dependencies |
| `Dockerfile` | Instructions to build the frontend container |

---

## Most Important Code

**`hooks/useWebSocket.ts`** — A generic React hook that opens a WebSocket connection to the server and automatically reconnects if it drops. Uses exponential backoff with jitter (e.g. wait 100ms, then 200ms, then 400ms — with some randomness so all clients don't reconnect at exactly the same time after an outage). The **`backoffDelay(baseDelay, attempt)`** function is exported separately for unit testing.

**`hooks/useMarketData.ts`** — Manages the single market data WebSocket (`/ws/market`) that all price panels share. Components don't open their own WebSocket connections — instead they call `useMarketData().subscribe(["AAPL", "MSFT"])` and the hook manages subscriptions to the shared connection. Received quotes are written to the `marketDataStore` so all panels update simultaneously.

**`middleware.ts`** — A Next.js Edge Middleware file that runs on every request before the page loads. It checks for the `qn-authed` cookie and redirects unauthenticated users to the login page before any JavaScript even loads.

---

## How to Run Locally (without Docker)

```bash
cd frontend

# Install dependencies
npm install

# Start the development server with hot-reload
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

---

## Testing

```bash
# Unit tests (Vitest — a fast JavaScript test runner)
npm run test

# End-to-end tests (Playwright — simulates a real browser clicking through the app)
npm run test:e2e

# Type checking (TypeScript — catches type errors without running the code)
npx tsc --noEmit

# Linting (ESLint — checks for code style issues)
npm run lint
```

---

## How does this connect to the rest of the app?

- Makes HTTP calls to `backend/app/api/v1/` via the functions in `lib/api/`
- Connects to `backend/app/api/ws/` WebSocket feeds for live data
- All state (prices, auth tokens, layout config) lives in `store/` — individual panels read from these stores rather than making their own API calls
- The `middleware.ts` file guards all routes, redirecting to `/login` if the user isn't authenticated
