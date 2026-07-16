# ADR-012 — FIX Protocol Integration Strategy

**Date:** 2025-07-15
**Status:** Accepted
**Authors:** QuantNexus Engineering

---

## Context

QuantNexus currently routes all equity orders through Alpaca's paper-trading REST API
and forex orders through OANDA's v20 REST API.  As the platform evolves toward
institutional-grade execution, a FIX (Financial Information eXchange) protocol adapter
will be required to connect to prime brokers, ECNs, and dark pools.

FIX is the industry standard for order routing at hedge funds, asset managers, and
proprietary trading desks.  The two leading open-source FIX libraries are:

| Library | Language | License |
|---------|----------|---------|
| [QuickFIX](https://github.com/quickfix/quickfix) | C++/Python | BSD-like (free) |
| [QuickFIX/n](https://github.com/connamara/quickfixn) | C# / .NET | Apache 2.0 |

---

## Decision

1. **QuickFIX (C++)** will be the integration target, matching the C++ engine in `engine/`.
2. The `engine/fix/fix_session.h` interface is intentionally abstract — the `FixSession`
   base class allows swapping the live `FixSessionQuickFIX` for the `FixSessionSimulated`
   in development and CI.
3. **No live FIX calls will be wired until the following criteria are met:**
   - Institutional brokerage relationship and FIX session credentials established.
   - Legal/compliance review complete (Reg NMS, MiFID II as applicable).
   - C++ engine (ADR-013) running in production under load for ≥ 30 days.
   - Platform kill-switch (D-2) confirmed to block all order paths end-to-end.

---

## Re-engagement Criteria

| Criterion | Owner | Status |
|-----------|-------|--------|
| Prime broker relationship signed | Business / Legal | ❌ Not started |
| FIX session credentials received | Infrastructure | ❌ Blocked on above |
| Compliance review complete | Legal | ❌ Not started |
| Kill-switch production-verified | Engineering | ✅ Implemented |
| C++ engine load-tested at 1M orders/day | Engineering | ❌ Not started |

---

## Consequences

### Positive
- Clean separation between the simulated and live FIX implementations.
- All production FIX logic is encapsulated in `engine/fix/` — zero impact on the
  Python backend until integration is explicitly activated.
- The `FixSessionSimulated` class allows full order-flow testing without a live broker.

### Negative
- FIX integration is a large standalone engineering effort (estimated 4–6 weeks).
- Requires dedicated network infrastructure (co-lo or proximity hosting) for
  sub-millisecond latency to be meaningful.
- Ongoing FIX session monitoring and heartbeat management add operational complexity.

---

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| REST-only order routing (Alpaca + OANDA) | Stays as primary for paper trading; inadequate for HFT |
| FIX via Python `quickfix` library | Acceptable performance for low-frequency; using C++ for consistency with the engine |
| FIX over a cloud broker API (e.g., Interactive Brokers TWS) | IB's API is proprietary; limits venue diversity |
