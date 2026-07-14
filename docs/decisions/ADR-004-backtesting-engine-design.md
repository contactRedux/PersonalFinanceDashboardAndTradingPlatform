# ADR-004: Backtesting Engine Design — Dual-Engine (Vectorized + Event-Driven)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2025-01-15 |
| **Deciders** | Platform team |
| **Supersedes** | — |

---

## Context

QuantNexus supports strategy development and validation through a backtesting
subsystem. Two distinct use cases drive the design:

1. **Parameter optimisation / screening** — running hundreds or thousands of
   parameter combinations over years of OHLCV data to find promising regimes.
   Speed is the primary constraint.

2. **Final validation runs** — single, careful runs of a specific strategy
   configuration intended to produce a realistic equity curve for review.
   Execution realism (slippage, partial fills, order queuing) is the primary
   constraint.

### Why one engine cannot serve both well

| Requirement | Vectorized | Event-Driven |
|---|---|---|
| Speed (10-year OHLCV, 1-min bars) | ✓ < 1 s | ✗ 60–120 s |
| Slippage model | ✗ approximated | ✓ exact per-fill |
| Partial fills | ✗ not modelled | ✓ order book simulation |
| Look-ahead bias prevention | ✓ by construction (NumPy shifts) | Requires careful event ordering |
| Grid / walk-forward optimisation | ✓ vectorised over param axes | ✗ prohibitively slow |

A vectorized engine operates on NumPy arrays of the full price history in one
pass — it is approximately **100× faster** than an equivalent event loop for
the same dataset, but cannot realistically model order execution details.

An event-driven engine processes one bar (or tick) at a time through an event
queue, accurately simulating the sequence in which a live system would receive
data and execute orders.

---

## Decision

Adopt a **dual-engine architecture**:

| Engine | Class | Use case |
|---|---|---|
| Vectorized | `VectorizedEngine` | Parameter grid search, factor screening, walk-forward windows |
| Event-Driven | `EventDrivenEngine` | Final validation, slippage-realistic equity curves, paper trading replay |

The two engines share a common `Strategy` interface and a common `BacktestResult`
output schema so results can be compared and displayed in the same UI.

Typical workflow:

```
1. VectorizedEngine  →  grid search over (fast_ma, slow_ma, stop_loss)
2. Select top-N parameter sets from results
3. EventDrivenEngine →  validate each set with realistic execution model
4. Present final equity curves + metrics in the UI
```

---

## Consequences

### Positive

- **Speed** — parameter optimisation that would take hours in an event loop
  completes in seconds with vectorised NumPy operations, enabling interactive
  exploration in the UI.
- **Realism** — final validation runs accurately model broker behaviour
  (variable slippage, fractional fills, order priority), producing equity
  curves that are representative of live performance.
- **Shared output schema** — `BacktestResult` (Sharpe, CAGR, max drawdown,
  trade log) is identical for both engines, so the UI requires no branching.

### Negative / trade-offs

- **Two code paths** — signal logic written for the vectorised engine must be
  re-expressed as event handlers for the event-driven engine. Divergence is
  possible if the two implementations are not kept in sync.
- **Result divergence** — a parameter set that looks excellent in the
  vectorised run may appear weaker after event-driven validation due to
  execution modelling differences. Users must understand this is expected
  and not a bug.
- **Vectorized look-ahead bias** — the vectorised engine prevents look-ahead
  bias by construction (all signals are computed with `.shift(1)` on the
  signal series), but custom user strategies that bypass the standard signal
  API could inadvertently introduce bias without triggering a warning.

### Mitigations

- A `StrategyAdapter` class auto-generates a `VectorizedEngine`-compatible
  signal array from an `EventDrivenEngine` strategy for simple strategies,
  reducing duplicated logic for common cases.
- An automated **consistency check** runs both engines on the same 1-year
  in-sample window for each new strategy; a Sharpe ratio divergence > 20 %
  raises a warning in the UI, prompting the user to investigate.
- The vectorised engine's signal pipeline is unit-tested with a synthetic
  price series that has a known look-ahead trigger, ensuring the `.shift(1)`
  guard is enforced.
