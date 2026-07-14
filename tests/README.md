# tests/ — Testing Guide

## What is this folder?

This folder contains tests that verify QuantNexus works correctly under real-world conditions, including high traffic. It complements the unit and integration tests that live closer to the code they test (in `backend/tests/` and `frontend/tests/`).

---

## Contents

```
tests/
├── load/
│   ├── ws_market.js    k6 load test: 1,000 concurrent WebSocket subscribers
│   └── rest_auth.js    k6 load test: 200 REST requests/second auth + API flow
└── e2e/                (placeholder — Playwright end-to-end tests)
```

---

## Load Tests (`tests/load/`)

**Load testing** simulates many users hitting the system at once to find performance bottlenecks before real users do. These tests use **k6** — an open-source load testing tool that runs JavaScript scenarios.

Think of it like a fire drill: you practice an emergency before it happens.

### `ws_market.js` — WebSocket Load Test

**Scenario:** 1,000 virtual users simultaneously connect to `/ws/market` and subscribe to 5 stock symbols each.

**Ramp-up:** 0 → 1,000 users in 10 seconds, hold for 20 seconds.

**Pass criteria:**
- `ws_msg_latency_ms p(99) < 100ms` — 99% of subscriptions receive their first message in under 100 milliseconds
- `ws_subscribe_errors == 0` — no connection failures

### `rest_auth.js` — REST Load Test

**Scenario:** Constant 200 requests/second through a realistic user flow: login → fetch portfolio → fetch quotes.

**Pass criteria:**
- `http_req_duration p(99) < 500ms` — 99% of requests complete in under 500 milliseconds
- `http_error_rate < 0.1%` — fewer than 1 in 1,000 requests returns an error

### Running the load tests

```bash
# Install k6 (macOS)
brew install k6

# Start the local stack first
docker compose up -d

# Run both load tests
make load-test

# Run individually
k6 run tests/load/ws_market.js
k6 run tests/load/rest_auth.js

# Target a different server
BASE_URL=https://staging.quantnexus.internal k6 run tests/load/rest_auth.js
```

k6 prints a summary at the end. Exit code `0` = all thresholds passed. Exit code `99` = a threshold failed (treat as a build failure in CI).

---

## Unit Tests

Unit tests live next to the code they test:

```bash
# Backend Python tests (pytest)
cd backend && uv run pytest tests/ -v

# Frontend TypeScript tests (Vitest)
cd frontend && npm run test
```

Backend tests are in `backend/tests/` and cover: API endpoints (using `httpx.AsyncClient` against the real FastAPI app), Celery tasks (with Redis/DB mocked), backtesting engine, ML model training/inference, and optimization algorithms.

Frontend tests are in `frontend/tests/` and cover: Zustand store behavior, utility functions, WebSocket hook reconnection logic, and component rendering.

---

## End-to-End Tests (`tests/e2e/`)

E2E (End-to-End) tests use **Playwright** to launch a real browser and simulate a complete user journey — log in, search for a stock, set an alert, run a backtest — clicking through the UI exactly as a human would.

> **Note:** The `tests/e2e/` directory is currently a placeholder. Playwright configuration lives in `frontend/playwright.config.ts` and test files go in `frontend/tests/`.

```bash
# Run E2E tests (requires the full stack to be running)
make test-e2e
# or
cd frontend && npm run test:e2e
```

For E2E tests, set `TEST_USER_EMAIL` and `TEST_USER_PASSWORD` in `.env` to a pre-registered test account.

---

## How does this connect to the rest of the app?

- Load tests target the backend WebSocket and REST endpoints defined in `backend/app/api/`
- The CI pipeline (`.github/workflows/`) runs `make test` (unit tests) and optionally `make load-test` on pull requests to prevent performance regressions
- Load test thresholds in `ws_market.js` and `rest_auth.js` define the performance SLA (Service Level Agreement — the minimum standard of performance the system must meet)
