# ADR-009 — Reuters / Refinitiv Data Integration

**Date:** 2025-07-11  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

QuantNexus requires high-quality, professional-grade news and reference data for institutional
and advanced retail trading strategies. Reuters / Refinitiv (now LSEG Data & Analytics) offers
three main integration paths for programmatic access:

1. **Refinitiv Data Library for Python (`refinitiv-data`)** — the official Python SDK for the
   LSEG/Refinitiv ecosystem. Provides real-time and historical news headlines, stories, ESG data,
   company fundamentals, and financial instrument reference data. Requires a paid Desktop
   (Workspace/Eikon), Platform (RDP), or Deployed (RTDS) license.

2. **Refinitiv News API (REST/WebSocket)** — direct HTTP + WebSocket access to the News
   Monitoring Service. Returns machine-readable news stories tagged with RICS, DRIS, topic
   codes, and relevance scores. Requires Platform license and an RDP App Key.

3. **Open Permission Model (free tier)** — a small subset of LSEG endpoints are available
   under a community access tier, but coverage is insufficient for production trading.

Alternative: The Reuters News API is available via content syndication agreements for
publishers; this is separate from the developer SDK and is not evaluated here.

### Key cost/complexity factors

| Tier | Approx. annual cost | Suitable for |
|------|---------------------|--------------|
| Desktop (Eikon / Workspace) | ~$24,000/seat | Single-user quant research |
| RDP Platform license | Negotiated enterprise | Multi-system integration |
| RTDS (deployed) | Negotiated enterprise | Low-latency production |

Because a Refinitiv license is a significant commercial commitment, the adapter is implemented
as a fully functional but **feature-flagged** module. It is disabled at runtime unless
`REFINITIV_APP_KEY` is configured. No license-gated Python packages are included in the main
dependency graph; the `refinitiv-data` SDK must be installed separately by operators with a
valid license.

## Decision

Implement a **license-ready stub adapter** (`backend/app/services/news/refinitiv.py`) that:

1. Guards all SDK imports with a `try/except ImportError` block. When the SDK is not installed,
   the adapter logs a debug message and returns empty results — no crash, no import error.
2. Checks for `REFINITIV_APP_KEY` at runtime. If the key is empty, the adapter skips
   all API calls and returns an empty list.
3. Is wired into the news aggregator with a feature-flag guard, so it participates in the
   aggregation pipeline automatically once the license and SDK are in place.
4. Documents the SDK installation command in this ADR and in the module docstring.

The `refinitiv-data` package is documented as an **optional/licensed dependency** in a comment
block in `pyproject.toml`. It must not be added to the `[project].dependencies` array because
`uv sync` / `pip install` would fail for operators without a license.

## Activation path

### 1. Obtain a Refinitiv / LSEG license

Contact LSEG sales (https://www.lseg.com/en/data-analytics/financial-data) or your existing
Bloomberg/Refinitiv relationship manager. Request an RDP (Refinitiv Data Platform) App Key.

### 2. Install the SDK (in the active virtual environment)

```bash
pip install refinitiv-data>=1.0.0
```

Or with uv:

```bash
uv pip install refinitiv-data>=1.0.0
```

### 3. Configure the environment variable

```
REFINITIV_APP_KEY=your-rdp-app-key-here
```

The adapter will activate automatically on the next server restart. No code changes are needed.

## Consequences

### Positive
- Zero impact on operators without a Refinitiv license — `import refinitiv.data` is guarded;
  the package is not in the dependency lockfile, so `uv sync` succeeds unconditionally
- Institutional users can activate premium Reuters news in < 5 minutes once a license is issued
- The stub provides a clear, tested integration point for future activation

### Negative
- Reuters news is unavailable until a paid license is acquired
- `refinitiv-data` SDK version pinning is the operator's responsibility (not managed by uv.lock)
- The SDK has its own `.refinitiv-data.config.json` credential file convention that must be
  managed separately from the `.env` pattern used by the rest of the platform

### Neutral
- All Redis caching, structlog patterns, and normalisation logic are already implemented in the
  stub, so activation requires only a license key, not a development sprint
