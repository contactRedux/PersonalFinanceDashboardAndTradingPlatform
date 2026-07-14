# Developer Guide: Adding Technical Indicators

This guide walks through the full process of adding a new technical indicator to QuantNexus —
from the TypeScript chart implementation through to the Python backend equivalent and unit tests.

---

## Overview

Indicators have two parallel implementations:

- **TypeScript** (`frontend/lib/indicators/index.ts`) — used by the `ChartCanvas` component to
  render indicator overlays on the Lightweight Charts canvas.
- **Python** (`backend/app/services/indicators/`) — used by the backtesting engine for signal
  calculation and by the `/api/v1/market/indicators/{symbol}` endpoint.

Both implementations must agree on the indicator's mathematical definition and handle edge cases
identically (e.g., returning `NaN` / `float('nan')` when the period exceeds available data).

---

## Step 1 — Write the TypeScript function

**File:** [`frontend/lib/indicators/index.ts`](../../frontend/lib/indicators/index.ts)

Add a pure function that takes numeric arrays and returns a numeric array. Rules:

- **No side effects.** Do not access global state, DOM, or external services.
- **No `any` types.** All parameters and return values must be explicitly typed.
- **Handle edge cases.** When `period > data.length`, return an array of `NaN` values of the
  same length as the input, so the chart series receives data in the correct shape.

```typescript
/**
 * My Indicator — description of what it computes.
 * @param closes  Array of closing prices, oldest first.
 * @param period  Lookback period.
 * @returns       Array of indicator values, same length as `closes`.
 *                Values are NaN where insufficient data exists.
 */
export function myIndicator(closes: number[], period: number): number[] {
  if (closes.length < period) {
    return closes.map(() => NaN);
  }

  const result: number[] = closes.map(() => NaN);
  for (let i = period - 1; i < closes.length; i++) {
    const window = closes.slice(i - period + 1, i + 1);
    result[i] = window.reduce((sum, v) => sum + v, 0) / period; // example: SMA
  }
  return result;
}
```

---

## Step 2 — Add to `INDICATOR_TYPES`

**File:** [`frontend/components/panels/ChartPanel/ChartToolbar.tsx`](../../frontend/components/panels/ChartPanel/ChartToolbar.tsx)

Locate the `INDICATOR_TYPES` array and append a new entry:

```typescript
{ label: "MyInd", type: "myindicator", defaultParams: { period: 14 } }
```

- `label` — Display name shown in the "Add Indicator" dropdown.
- `type` — Internal string key; must be unique and lowercase.
- `defaultParams` — Pre-populated parameter values in the indicator settings dialog.

---

## Step 3 — Wire in ChartCanvas

**File:** [`frontend/components/panels/ChartPanel/ChartCanvas.tsx`](../../frontend/components/panels/ChartPanel/ChartCanvas.tsx)

Find the `useEffect` block that loops over the `indicators` prop and adds series to the chart.
Add a `case` for your indicator type:

### Single-value indicators (one line, price scale overlay)

```typescript
case "myindicator": {
  const values = myIndicator(closes, indicator.params.period ?? 14);
  const series = chart.addLineSeries({
    color: "#a78bfa",
    lineWidth: 1,
    priceScaleId: "myindicator",
    title: `MyInd(${indicator.params.period})`,
  });
  series.setData(
    values.map((v, i) => ({ time: times[i], value: v })).filter((d) => !isNaN(d.value))
  );
  break;
}
```

### Multi-line indicators (e.g., upper/lower bands)

Follow the pattern used for Bollinger Bands (`"bb"` case): create two `LineSeries` instances
sharing a `priceScaleId`, one for the upper band and one for the lower band. An area fill
between them can be added by using `addAreaSeries` for the upper and setting
`topColor`/`bottomColor` to a semi-transparent value.

---

## Step 4 — Add the Python equivalent

**File:** `backend/app/services/indicators/momentum.py` (or create a new module)

Mirror the TypeScript function using numpy arrays. The function signature uses the same
parameter names as the TypeScript version:

```python
import numpy as np


def my_indicator(closes: np.ndarray, period: int) -> np.ndarray:
    """
    My Indicator — description.

    Args:
        closes: 1-D array of closing prices, oldest first.
        period: Lookback period.

    Returns:
        1-D array of indicator values, same length as closes.
        Values are np.nan where insufficient data exists.
    """
    if len(closes) < period:
        return np.full(len(closes), np.nan)

    result = np.full(len(closes), np.nan)
    for i in range(period - 1, len(closes)):
        result[i] = closes[i - period + 1 : i + 1].mean()
    return result
```

If the indicator is used for signal generation in a backtest strategy, import it from the
appropriate strategy file in `backtesting/strategies/`.

---

## Step 5 — Write unit tests

**File:** [`frontend/tests/unit/indicators.test.ts`](../../frontend/tests/unit/indicators.test.ts)

Minimum two assertions per indicator:

```typescript
import { describe, it, expect } from "vitest";
import { myIndicator } from "../../lib/indicators";

describe("myIndicator", () => {
  it("returns the correct value for a known input", () => {
    const closes = [10, 20, 30, 40, 50];
    const result = myIndicator(closes, 3);
    // 3-period SMA of last window [30, 40, 50] = 40
    expect(result[4]).toBeCloseTo(40, 5);
  });

  it("returns NaN for all values when period > data length", () => {
    const result = myIndicator([10, 20], 5);
    expect(result.every((v) => isNaN(v))).toBe(true);
  });
});
```

---

## Step 6 — Verify TypeScript

Run the TypeScript compiler in check-only mode from the `frontend` directory:

```bash
cd frontend && npx tsc --noEmit
```

Fix any type errors before proceeding. Common issues:
- Forgetting to export the function from `index.ts`
- Missing the `case` in the `switch` statement inside `ChartCanvas.tsx`
- Incorrect type on `indicator.params` (add the new param key to the `IndicatorParams` type if
  one exists)

---

## Step 7 — Run Vitest

```bash
cd frontend && npx vitest run
```

All existing tests must continue to pass. The new indicator tests must appear in the output with
a green ✓.

---

## Checklist

- [ ] TypeScript function added to `frontend/lib/indicators/index.ts` — pure, no `any`, NaN on edge case
- [ ] Entry added to `INDICATOR_TYPES` in `ChartToolbar.tsx`
- [ ] `case` block added in `ChartCanvas.tsx` indicators `useEffect`
- [ ] Python equivalent added to `backend/app/services/indicators/`
- [ ] Unit tests written (`indicators.test.ts`) — known value + edge case
- [ ] `npx tsc --noEmit` passes with zero errors
- [ ] `npx vitest run` passes with zero failures
