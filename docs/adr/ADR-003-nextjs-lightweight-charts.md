# ADR-003 — Next.js 15 + TradingView Lightweight Charts

**Date:** 2025-01-10  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The frontend requires two rendering modes that cannot be satisfied by a single-page application
alone: server-side rendering (SSR) for authentication pages (login, register) to enable proper
SEO and immediate content delivery, and client-side rendering (CSR) with live WebSocket
connections for the interactive dashboard panels (charts, order book, portfolio). The charting
component must handle 10,000+ OHLCV data points and real-time tick updates without frame drops
on standard consumer hardware.

Three candidate approaches were evaluated. A pure SPA with Create React App (or Vite) provides
the CSR half but requires a separate solution (a dedicated SSR service or a CDN-served static
shell) for auth pages. Next.js with the Pages Router satisfies both modes but its data-fetching
patterns (`getServerSideProps`, `getStaticProps`) are less composable than React Server
Components for complex nested layouts. Next.js 15 with the App Router provides the cleanest
hybrid: Server Components for SSR layouts and auth pages, Client Components for live-data
panels.

For charting, three libraries were assessed: Chart.js, Recharts, and TradingView Lightweight
Charts. Chart.js and Recharts render to an HTML `<canvas>` or SVG but struggle to maintain 60
fps when streaming hundreds of new data points per second. Lightweight Charts is a WebGL/Canvas
library purpose-built for financial time-series; it was designed to handle the exact workload
described here.

## Decision

Use **Next.js 15 with the App Router** for the frontend framework and **lightweight-charts v5**
(the TradingView open-source library) for all candlestick and line-chart rendering.

Next.js 15 App Router enables a clean separation: auth-related routes under `app/(auth)/` are
Server Components rendered on the Node.js server and sent as complete HTML; dashboard routes
under `app/(dashboard)/` are Client Components that establish WebSocket connections and manage
local state. TypeScript support is first-class and no additional Babel configuration is needed.
Lightweight Charts v5 is TypeScript-native, ships its own type definitions, and supports all
required chart types: candlestick, line, area, histogram (volume), and Baseline series.

## Consequences

### Positive
- Hybrid rendering: SSR for auth (SEO, TTFB), CSR for trading panels (real-time updates)
- Lightweight Charts handles 10,000+ bars and streaming ticks with no perceptible frame drops
- TypeScript-native stack end-to-end: frontend, backend Pydantic schemas, chart library types
- Next.js App Router's layout system enables persistent panels (sidebar, header) across
  navigations without full re-mounts
- Auto-generated API routes in Next.js can proxy sensitive backend calls without exposing
  credentials to the browser

### Negative
- App Router introduces React Server Components: the mental model (server vs. client boundary,
  `"use client"` directives, async Server Component data fetching) has a steeper learning curve
  than the Pages Router
- Lightweight Charts does not support all exotic chart types (Renko, N-Line Break) natively;
  these are computed server-side and rendered as standard OHLCV candlestick data
- Next.js 15 with App Router has breaking changes from Next.js 13/14; documentation examples
  online are mixed across versions

### Neutral
- Node.js 22 is required as the runtime (LTS at time of decision)
- The frontend build (`npm run build`) produces a standalone output configured for Docker
  deployment behind the Nginx reverse proxy
