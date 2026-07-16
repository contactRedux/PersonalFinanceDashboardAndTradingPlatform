# ADR-010 — Institutional Data Vendor Strategy

**Date:** 2025-07-11  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Institutional-grade fundamental data (financial statements, estimates, segment data, ownership)
is provided by a set of commercial vendors with widely varying access models, pricing, and
API quality. QuantNexus currently uses Financial Modeling Prep (FMP) as its primary fundamentals
source. This ADR evaluates the major institutional alternatives and documents the FactSet
integration decision.

### Vendor comparison

| Vendor | Access model | Free tier | API style | Notes |
|--------|-------------|-----------|-----------|-------|
| **FactSet** | API key; Open FactSet developer tier (free, rate-limited) | ✓ | REST/JSON | Best-in-class estimates; 250 req/day free |
| **Morningstar** | Institutional license only | ✗ | REST | Used by ETF/fund managers; no developer API |
| **Capital IQ** (S&P Global) | Institutional license only | ✗ | Excel plug-in / REST | Strong M&A/private data; not API-first |
| **PitchBook** | Institutional license only | ✗ | REST (limited) | VC/PE/private market focus |
| **eMoney** | Financial advisor platform | ✗ | Proprietary | Wealth management, not trading data |

### FactSet Open API

FactSet's Open FactSet Marketplace (https://developer.factset.com) offers a free developer
tier with access to:
- Company facts and profiles
- Time series fundamentals (annual/quarterly income statement, balance sheet, cash flow)
- Consensus estimates (EPS, revenue, EBITDA forward estimates)
- Entity identifiers (FactSet Entity ID, SEDOL, ISIN mapping)

Rate limits on the free developer tier: ~250 requests/day. The API uses HTTP Basic Auth
with an API key in the `username:apikey` format.

### Morningstar

Morningstar's data is available only through institutional data agreements or the Morningstar
Direct platform. There is no public developer API. Integration requires a commercial partnership
and custom data delivery (SFTP feed or private REST endpoint). Deferred to future enterprise tier.

### Capital IQ / S&P Global

S&P Global Market Intelligence (Capital IQ) requires an institutional license. Their API
(Xpressfeed, SNL, CIQ) is accessible only through licensed agreements. The data is exceptionally
strong for M&A comps and private company data but not suitable for a self-service developer
platform at the current stage. Deferred.

### PitchBook

PitchBook Data provides private market, VC, and PE transaction data. While an API exists, it
requires an enterprise subscription and is not focused on public-equity fundamentals. Deferred.

### eMoney

eMoney Advisor is a financial planning platform for registered investment advisors. It does not
provide market data APIs. Out of scope.

## Decision

Implement **FactSet Open API** integration as an optional secondary fundamentals source
(`backend/app/services/fundamentals/factset.py`). The adapter:

1. Requires `FACTSET_API_KEY` to be set; returns empty data gracefully when absent.
2. Is wired into `GET /fundamentals/{symbol}` as a secondary source, called only when FMP
   returns no data for a symbol (or when FMP is also unconfigured).
3. Uses the same Redis caching and structlog patterns as the FMP adapter.
4. Is fully tested with mocked HTTP responses.

Morningstar, Capital IQ, PitchBook, and eMoney are documented here as deferred decisions.
They will be reconsidered when QuantNexus reaches institutional client tiers that justify
the licensing cost.

## Consequences

### Positive
- FactSet free developer tier provides high-quality institutional estimates at no cost for
  development and low-volume production use
- Optional wiring means no disruption to FMP-dependent production deployments
- Clear upgrade path: swapping to a paid FactSet tier requires only an API key change

### Negative
- Free FactSet tier is limited to 250 requests/day — production throughput requires a paid plan
- FactSet API uses HTTP Basic Auth; credentials must be stored securely in `FACTSET_API_KEY`
  as `username:apikey` format
- Morningstar/Capital IQ data gaps (private market, detailed segment breakdowns) remain

### Neutral
- FactSet entity IDs (FactSet ID, SEDOL) are additional identifiers not currently used by the
  platform; they may be relevant for multi-venue order routing (see ADR-011 for FIGI/ISIN)
