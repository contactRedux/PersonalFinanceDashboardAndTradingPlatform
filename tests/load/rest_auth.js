/**
 * k6 REST load test — Auth + Portfolio flow
 *
 * Constant arrival rate: 200 requests / second.
 * Flow per iteration:
 *   POST /api/v1/auth/login  →  store token
 *   GET  /api/v1/portfolio
 *   GET  /api/v1/orders
 *   GET  /api/v1/watchlist
 *   GET  /api/v1/market/quote/AAPL
 *
 * Pass criteria:
 *   - http_req_duration p(99) < 500 ms
 *   - error rate < 0.1 %
 *
 * Run:
 *   k6 run tests/load/rest_auth.js
 *   BASE_URL=https://staging.example.com k6 run tests/load/rest_auth.js
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const errorRate = new Rate("http_error_rate");

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    constant_rps: {
      executor: "constant-arrival-rate",
      rate: 200,            // 200 iterations / second
      timeUnit: "1s",
      duration: "30s",
      preAllocatedVUs: 50,  // warm pool
      maxVUs: 300,          // ceiling for burst headroom
    },
  },
  thresholds: {
    http_req_duration: ["p(99)<500"],  // p99 < 500 ms
    http_error_rate: ["rate<0.001"],   // < 0.1 % errors
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Test credentials — override via env vars in CI.
const TEST_USER = __ENV.TEST_USER || "loadtest@example.com";
const TEST_PASS = __ENV.TEST_PASS || "loadtest_password";

// ── Helpers ───────────────────────────────────────────────────────────────────
function jsonHeaders(token) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return { headers };
}

function recordResult(res, label) {
  const ok = res.status >= 200 && res.status < 300;
  errorRate.add(!ok);
  check(res, {
    [`${label} status 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${label} body not empty`]: (r) => r.body && r.body.length > 0,
  });
  return ok;
}

// ── Main VU function ──────────────────────────────────────────────────────────
export default function () {
  // ── Step 1: Login ──────────────────────────────────────────────────────────
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: TEST_USER, password: TEST_PASS }),
    jsonHeaders(null)
  );

  const loginOk = recordResult(loginRes, "POST /auth/login");

  // Bail early if login failed — subsequent requests would also fail.
  if (!loginOk) {
    return;
  }

  let token = null;
  try {
    token = JSON.parse(loginRes.body).access_token;
  } catch (_) {
    errorRate.add(1);
    return;
  }

  // ── Step 2: Portfolio ──────────────────────────────────────────────────────
  recordResult(
    http.get(`${BASE_URL}/api/v1/portfolio`, jsonHeaders(token)),
    "GET /portfolio"
  );

  // ── Step 3: Orders ─────────────────────────────────────────────────────────
  recordResult(
    http.get(`${BASE_URL}/api/v1/orders`, jsonHeaders(token)),
    "GET /orders"
  );

  // ── Step 4: Watchlist ──────────────────────────────────────────────────────
  recordResult(
    http.get(`${BASE_URL}/api/v1/watchlist`, jsonHeaders(token)),
    "GET /watchlist"
  );

  // ── Step 5: Market quote ───────────────────────────────────────────────────
  recordResult(
    http.get(`${BASE_URL}/api/v1/market/quote/AAPL`, jsonHeaders(token)),
    "GET /market/quote/AAPL"
  );
}
