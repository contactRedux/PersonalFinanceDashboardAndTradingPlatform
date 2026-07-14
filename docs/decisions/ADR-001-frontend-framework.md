# ADR-001: Frontend Framework — Next.js 16 App Router

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2025-01-15 |
| **Deciders** | Platform team |
| **Supersedes** | — |

---

## Context

The QuantNexus frontend must satisfy competing requirements:

- **SEO & initial paint** — marketing pages, instrument detail pages, and
  shareable portfolio snapshots need server-rendered HTML for crawlers and a
  fast First Contentful Paint (FCP) for users arriving from search or social.
- **Rich interactivity** — the trading dashboard requires real-time WebSocket
  feeds, complex charting, and sub-second UI updates.
- **Full-stack integration** — API route handlers, auth middleware, and edge
  functions are preferable over maintaining a separate BFF layer.

### Alternatives evaluated

| Option | SSR | Server Components | File-based routing | Streaming | Notes |
|---|---|---|---|---|---|
| **Create React App (CRA)** | ✗ | ✗ | ✗ | ✗ | No longer maintained; client-only |
| **Vite + React** | Partial (manual) | ✗ | ✗ | ✗ | Excellent DX but no built-in SSR conventions |
| **Remix** | ✓ | ✗ | ✓ | ✓ | Strong data-loading model; smaller ecosystem |
| **Nuxt 3** | ✓ | ✓ | ✓ | ✓ | Vue 3 — team has deeper React expertise |
| **Next.js 16 App Router** | ✓ | ✓ | ✓ | ✓ | Largest ecosystem; RSC stable in v15/16 |

---

## Decision

**Next.js 16 with the App Router** is the frontend framework for QuantNexus.

Key reasons:

1. **React Server Components (RSC)** let data-heavy pages (instrument screener,
   portfolio summary) fetch data on the server with zero client JavaScript for
   the static shell, improving FCP and Time to Interactive.
2. **Streaming with Suspense** allows the dashboard shell to render immediately
   while chart data streams in, avoiding a full-page loading spinner.
3. **Built-in API routes & middleware** eliminate a separate BFF service for
   auth token validation, rate limiting, and WebSocket upgrade proxying.
4. **App Router conventions** (layouts, loading, error boundaries) provide
   consistent patterns across the team without additional architecture
   decisions per route.

---

## Consequences

### Positive

- Server components handle data fetching; client bundle stays small for
  publicly cached pages.
- Vercel deployment is zero-config; Docker deployment via `next start` is
  equally well-supported.
- Large community, extensive third-party library compatibility.

### Negative / trade-offs

- **"use client" boundary discipline** — every interactive component (charts,
  order forms, WebSocket consumers) must be explicitly marked `"use client"`.
  Forgetting this on a component that uses browser APIs produces a
  hard-to-debug hydration error.
- **App Router maturity** — some third-party libraries still assume Pages Router
  conventions; wrappers or patches may be needed.
- **Vercel coupling risk** — advanced features (edge middleware, ISR, image
  optimisation) are easiest on Vercel; self-hosted deployments require
  attention to replication of those behaviours.

### Mitigations

- `eslint-plugin-react-server-components` is enabled to lint `"use client"`
  boundaries in CI.
- The `next.config.js` `output: "standalone"` mode is used to keep the Docker
  image portable and Vercel-independent.
