# ADR-013 — C++ Execution Engine Architecture

**Date:** 2025-07-15
**Status:** Accepted
**Authors:** QuantNexus Engineering

---

## Context

The Python-based backtesting and paper-trading stack in `backend/` handles all current
production load.  As QuantNexus evolves toward intraday and high-frequency strategies,
Python dispatch latency (typically 1–5 ms per order round-trip) becomes a bottleneck for:

- Strategies that make > 100 decisions per second.
- Tick-by-tick backtesting replaying millions of prints at realistic throughput.
- Lock-free order book maintenance under high-frequency L2 updates.

The C++ engine (`engine/`) addresses these constraints.

---

## Architecture

```
Python Strategy / ML Layer
  (signals from LSTM / XGBoost / TFT models)
         │ pybind11 (< 1µs overhead)
         ▼
   C++ Engine  (engine/)
   ┌──────────────────────────────────────────┐
   │  OrderBook  (lock-free L2, shared_mutex) │
   │  RiskManager (pre-trade checks, < 500ns) │
   │  OrderManager (kill-switch, fill events) │
   │  FixSession (abstract; Simulated / Live) │
   └──────────────────────────────────────────┘
         │
         ▼
   Execution Venue
   (Alpaca paper REST → FIX broker when ADR-012 conditions met)
```

---

## Component Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| C++ standard | C++20 | `std::jthread`, `std::atomic_ref`, concepts |
| Shared state | `std::shared_mutex` | Phase 1; replace with Hazard Pointers in Phase 2 |
| Python bridge | pybind11 | Header-only, CMake-native, mature ecosystem |
| Build system | CMake ≥ 3.21 | `FetchContent` for GTest; cross-platform |
| Unit tests | Google Test | Industry standard; integrates with CTest/ctest |

---

## Phased Rollout

| Phase | Description | Pre-requisite |
|-------|-------------|---------------|
| F-1 (current) | Scaffolding, headers, Python fallback stubs | ✅ Complete |
| F-2 (current) | Lock-free order book (`shared_mutex` phase) | ✅ Complete |
| F-3 (deferred) | FIX protocol integration | ADR-012 criteria met |
| F-4 (future) | Hazard Pointer lock-free upgrade | Production benchmarks showing contention |
| F-5 (future) | Tick-replay backtesting at C++ speed | 30+ days of tick data accumulated |

---

## Re-engagement Criteria for Production Deployment

1. Python platform has sustained daily active users > 100.
2. Profiling confirms Python order dispatch (not I/O) is the measured bottleneck.
3. CMake + pybind11 installed in the production build pipeline.
4. C++ unit tests (GTest) passing in CI.
5. Python fallback stubs validated against the compiled .so interface.

---

## Consequences

### Positive
- Python strategies remain unchanged — the bridge is transparent.
- The Python fallback stubs allow CI testing without a C++ build environment.
- The kill-switch is implemented at both the C++ engine level
  (atomic flag in `OrderManager`) and the Python API level (Redis flag in `admin.py`),
  providing defence-in-depth.

### Negative
- Adds a C++ build step to the development workflow.
- Requires macOS/Linux developers to install CMake + pybind11 (`brew install cmake pybind11`).
- Two codebases (Python + C++) must be kept in sync at the interface boundary.
