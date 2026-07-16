# ADR-011 — Bloomberg / OpenFIGI Identifier Enrichment

**Date:** 2025-07-11  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Financial instrument identifiers are fragmented across ecosystems: tickers differ between
exchanges and data providers; ISIN, CUSIP, SEDOL, and FIGI each serve different regulatory and
operational contexts. When QuantNexus users search for symbols, enriching results with
standardised identifiers improves interoperability with prime brokers, clearing houses, and
reporting tools.

### Bloomberg Terminal / B-PIPE / Bloomberg Data License

Bloomberg is the gold standard for financial data. Access options are:

| Product | Description | Cost |
|---------|-------------|------|
| Bloomberg Terminal | GUI desktop product | ~$27,000/user/year |
| B-PIPE (Bloomberg Professional API) | Server-side real-time data feed | Enterprise pricing |
| Bloomberg Data License (BDL) | Batch historical data delivery | Enterprise pricing |
| Bloomberg AlphaSpace | Quant research platform with REST API | Negotiated per use case |

All Bloomberg products require institutional agreements. There is no developer or free tier.
Integration is deferred until QuantNexus reaches institutional client scale.

### OpenFIGI (Bloomberg Open Symbology)

Bloomberg open-sourced its **Financial Instrument Global Identifier (FIGI)** system.
OpenFIGI (https://www.openfigi.com) provides a **free, no-key REST API** for identifier
mapping (ticker + exchange → FIGI, ISIN, CUSIP, SEDOL, name, security type, market sector).

Rate limits without an API key: **10 requests per minute**. An optional API key raises this
to **25 requests per minute** (free registration at https://www.openfigi.com/api).

OpenFIGI supports bulk mapping: up to 100 identifiers per request body. This allows a single
API call to enrich an entire search results page.

### Decision rationale

OpenFIGI directly implements Bloomberg's FIGI standard and is maintained by Bloomberg LP as
a public-good service. It provides FIGI, ISIN, CUSIP, and SEDOL — the four identifiers most
commonly required by prime brokers and regulatory reporting. Integration cost is zero (no
license, no negotiation), and the endpoint is stable (used by hundreds of fintech platforms).

Bloomberg Terminal, B-PIPE, and AlphaSpace are documented as **deferred** decisions. They will
be re-evaluated when QuantNexus serves institutional clients with Bloomberg contracts.

## Decision

Implement **OpenFIGI adapter** (`backend/app/services/fundamentals/openfigi.py`) that:

1. Calls `POST https://api.openfigi.com/v3/mapping` to map `(ticker, exchange)` to
   `{figi, isin, cusip, name, securityType, marketSector}`.
2. Supports an optional `OPENFIGI_API_KEY` (raises rate limit from 10 to 25 req/min).
3. Caches results in Redis with a 24-hour TTL (FIGI identifiers are stable).
4. Is wired into `GET /api/v1/market/search` to enrich results with FIGI/ISIN/CUSIP.
5. Fails gracefully: if OpenFIGI is unavailable, search results are returned without enrichment.

## Consequences

### Positive
- FIGI, ISIN, CUSIP, and SEDOL enrichment with zero licensing cost
- Bloomberg-maintained standard — widely accepted by prime brokers and clearing houses
- 24-hour Redis cache makes the 10 req/min rate limit inconsequential for typical search volumes
- Paves the way for Bloomberg Terminal integration: FIGI is the native Bloomberg identifier,
  so the data model is already aligned

### Negative
- Rate limit (10 req/min without key, 25 req/min with key) means high-volume symbol lookups
  (e.g. screener with 500+ results) may hit limits before cache population is complete
- OpenFIGI does not cover all instruments (derivatives, structured products have partial coverage)
- CUSIP data requires a separate CUSIP Global Services license for redistribution; OpenFIGI
  provides CUSIP only for display purposes, not for downstream distribution

### Neutral
- Bloomberg Terminal integration (when pursued) would use the same FIGI identifier values
  already stored via OpenFIGI, so no data migration is needed
- `OPENFIGI_API_KEY` registration is free at https://www.openfigi.com/api and takes < 5 minutes
