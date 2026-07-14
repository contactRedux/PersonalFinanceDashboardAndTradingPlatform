# ADR-003: WebSocket Architecture — Single Connection + Zustand Fan-out

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2025-01-15 |
| **Deciders** | Platform team |
| **Supersedes** | — |

---

## Context

The QuantNexus trading dashboard contains multiple panels that all consume
real-time market data simultaneously:

- Live Quotes panel
- Candlestick chart
- Order book depth visualisation
- Positions / P&L ticker
- Watchlist with live prices
- Alert monitor

### Problem with naïve per-component connections

If each panel opened its own WebSocket connection to `/ws/market`, a fully
loaded dashboard would establish **6 or more simultaneous connections per
browser tab**. This causes three problems:

1. **Browser WebSocket limit** — browsers limit concurrent connections per
   origin (typically 6–256 depending on browser); other tabs and browser
   features also consume from this pool.
2. **Server resource consumption** — each connection requires a file
   descriptor, a Redis subscription, and a goroutine/asyncio task on the
   server. Multiplying by the number of users quickly exhausts resources.
3. **Inconsistency** — panels that open separate connections may receive
   the same tick at slightly different times, causing the chart and the
   quotes panel to briefly show different prices for the same symbol.

### Alternatives evaluated

| Approach | Connections | Consistency | Complexity |
|---|---|---|---|
| Per-component WebSocket | N per tab | Low (race conditions) | Low (local) |
| Shared Worker + MessageChannel | 1 per origin | High | High (Worker API) |
| Server-Sent Events (SSE) | 1 per tab | High | Medium |
| **Single WS + Zustand fan-out** | 1 per tab | High | Low–Medium |

SSE was rejected because it is unidirectional (no subscribe/unsubscribe
messages from the client). Shared Worker was rejected due to limited Safari
support at the time of the decision.

---

## Decision

**One WebSocket connection per browser tab**, managed by a
`MarketDataProvider` React context. All panels subscribe to slices of the
`marketDataStore` Zustand store rather than directly to the socket.

Architecture:

```
Browser tab
└── MarketDataProvider (React context)
    ├── opens single WebSocket → /ws/market
    ├── sends subscribe { symbols: [...] } messages
    └── on message: calls marketDataStore.setQuote(symbol, tick)

Zustand marketDataStore
├── quotes: Record<symbol, Tick>        ← panels read this
├── orderbook: Record<symbol, Depth>
└── actions: subscribe / unsubscribe

Dashboard panels (any number)
└── useMarketData(symbol) hook → reads from Zustand slice
    (re-renders only when that symbol's data changes)
```

---

## Consequences

### Positive

- **Single connection per tab** — server load scales with the number of
  browser tabs, not the number of panels per tab.
- **Atomic updates** — all panels reading from Zustand observe the same
  tick simultaneously; chart and quotes panel can never disagree.
- **Simple reconnect logic** — only `MarketDataProvider` needs reconnection
  logic (exponential backoff); panels are unaware of the transport layer.
- **Selective re-renders** — Zustand's selector pattern ensures a panel
  subscribed to `AAPL` does not re-render when a `TSLA` tick arrives.

### Negative / trade-offs

- **`MarketDataProvider` is a single point of failure** — a bug in the
  provider can break all panels at once.
- **Zustand slices must stay lightweight** — storing raw tick history
  in the store would cause large state diffs and slow renders; panels
  needing historical data must fetch it separately via REST or a charting
  library's own buffer.
- **Symbol subscription management** — the provider must track which
  symbols are currently needed (union of all panel subscriptions) and
  send `unsubscribe` messages when no panel needs a symbol, to avoid
  receiving and processing unused ticks.

### Mitigations

- `MarketDataProvider` has a dedicated integration test suite with a
  mock WebSocket server.
- A `useMarketDataSubscription(symbols)` hook abstracts
  subscribe/unsubscribe lifecycle so individual panels never manipulate
  the socket directly.
