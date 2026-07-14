/**
 * k6 WebSocket load test — /ws/market
 *
 * Simulates 1 000 concurrent users each subscribing to 5 symbols.
 * Ramp: 0 → 1 000 VUs over 10 s, hold for 20 s.
 * Pass criteria: p(99) message latency < 100 ms.
 *
 * Run:
 *   k6 run tests/load/ws_market.js
 *   BASE_URL=ws://staging.example.com k6 run tests/load/ws_market.js
 */

import ws from "k6/ws";
import { check, sleep } from "k6";
import { Trend, Counter } from "k6/metrics";

// ── Custom metrics ────────────────────────────────────────────────────────────
const msgLatency = new Trend("ws_msg_latency_ms", true);
const msgReceived = new Counter("ws_messages_received");
const subErrors = new Counter("ws_subscribe_errors");

// ── Test configuration ────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: "10s", target: 1000 }, // ramp up
    { duration: "20s", target: 1000 }, // hold
  ],
  thresholds: {
    ws_msg_latency_ms: ["p(99)<100"], // p99 latency < 100 ms
    ws_subscribe_errors: ["count==0"],
  },
};

const BASE_URL = __ENV.BASE_URL || "ws://localhost:8000";
const WS_URL = `${BASE_URL}/ws/market`;

const SUBSCRIBE_PAYLOAD = JSON.stringify({
  type: "subscribe",
  symbols: ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"],
});

// ── Main VU function ──────────────────────────────────────────────────────────
export default function () {
  const res = ws.connect(WS_URL, {}, function (socket) {
    // Track when each symbol message was requested so we can measure latency.
    let subscribeTime = null;

    socket.on("open", function () {
      subscribeTime = Date.now();
      socket.send(SUBSCRIBE_PAYLOAD);
    });

    socket.on("message", function (data) {
      const now = Date.now();
      msgReceived.add(1);

      // Measure latency from subscribe send to first message receipt.
      if (subscribeTime !== null) {
        msgLatency.add(now - subscribeTime);
        subscribeTime = null; // only measure first message per subscription
      }

      // Validate message is parseable JSON with an expected shape.
      let msg;
      try {
        msg = JSON.parse(data);
      } catch (_) {
        subErrors.add(1);
        return;
      }

      check(msg, {
        "message has type field": (m) => m.type !== undefined,
        "message has symbol field": (m) => m.symbol !== undefined,
      });
    });

    socket.on("error", function (e) {
      subErrors.add(1);
      console.error(`WS error: ${e.error()}`);
    });

    // Hold the connection open for the duration of the test stage.
    socket.setTimeout(function () {
      socket.close();
    }, 30000);
  });

  check(res, {
    "WebSocket connected (101)": (r) => r && r.status === 101,
  });
}
