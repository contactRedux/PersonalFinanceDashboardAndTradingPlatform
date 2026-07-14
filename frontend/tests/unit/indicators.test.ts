/**
 * Unit tests for technical indicator compute functions.
 */
import { describe, it, expect } from "vitest";
import { sma, ema, rsi, macd, bollingerBands, atr, vwap, obv, heikinAshi } from "@/lib/indicators";

// Sample OHLCV data (20 bars of synthetic data)
const close = [
  100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
  110, 108, 111, 113, 112, 114, 116, 115, 117, 119,
];
const high = close.map((c) => c + 1.5);
const low = close.map((c) => c - 1.5);
const volume = close.map(() => 1_000_000);

describe("SMA", () => {
  it("returns NaN for periods before period-1", () => {
    const result = sma(close, 5);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[3])).toBe(true);
  });

  it("computes correct SMA at period-1 index", () => {
    const result = sma(close, 5);
    const expected = (100 + 102 + 101 + 103 + 105) / 5;
    expect(result[4]).toBeCloseTo(expected, 4);
  });

  it("result array has same length as input", () => {
    expect(sma(close, 3).length).toBe(close.length);
  });
});

describe("EMA", () => {
  it("returns NaN before first period", () => {
    const result = ema(close, 5);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[3])).toBe(true);
  });

  it("EMA seed equals SMA at first valid index", () => {
    const result = ema(close, 5);
    const smaResult = sma(close, 5);
    // Seed is SMA — first valid EMA value should equal SMA seed
    expect(result[4]).toBeCloseTo(smaResult[4], 4);
  });
});

describe("RSI", () => {
  it("returns NaN before period", () => {
    const result = rsi(close, 14);
    for (let i = 0; i < 14; i++) {
      expect(isNaN(result[i])).toBe(true);
    }
  });

  it("returns values in 0-100 range", () => {
    const result = rsi(close, 5);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
  });
});

describe("MACD", () => {
  it("returns correct structure", () => {
    const result = macd(close, 3, 6, 3);
    expect(result).toHaveProperty("macd");
    expect(result).toHaveProperty("signal");
    expect(result).toHaveProperty("histogram");
    expect(result.macd.length).toBe(close.length);
  });

  it("histogram = macd - signal where both defined", () => {
    const result = macd(close, 3, 6, 3);
    for (let i = 0; i < close.length; i++) {
      if (!isNaN(result.macd[i]) && !isNaN(result.signal[i])) {
        expect(result.histogram[i]).toBeCloseTo(
          result.macd[i] - result.signal[i],
          6
        );
      }
    }
  });
});

describe("Bollinger Bands", () => {
  it("upper > middle > lower for valid values", () => {
    const result = bollingerBands(close, 5, 2);
    for (let i = 4; i < close.length; i++) {
      expect(result.upper[i]).toBeGreaterThan(result.middle[i]);
      expect(result.middle[i]).toBeGreaterThan(result.lower[i]);
    }
  });
});

describe("ATR", () => {
  it("all valid ATR values are positive", () => {
    const result = atr(high, low, close, 5);
    for (const v of result) {
      if (!isNaN(v)) expect(v).toBeGreaterThan(0);
    }
  });
});

describe("VWAP", () => {
  it("returns array of same length", () => {
    const result = vwap(high, low, close, volume);
    expect(result.length).toBe(close.length);
  });

  it("vwap first value equals typical price of first bar", () => {
    const result = vwap(high, low, close, volume);
    const expectedFirst = (high[0] + low[0] + close[0]) / 3;
    expect(result[0]).toBeCloseTo(expectedFirst, 4);
  });

  it("vwap is positive for all values", () => {
    const result = vwap(high, low, close, volume);
    for (const v of result) {
      if (!isNaN(v)) expect(v).toBeGreaterThan(0);
    }
  });
});

describe("OBV", () => {
  it("starts with first volume value", () => {
    const result = obv(close, volume);
    expect(result[0]).toBe(volume[0]);
  });

  it("increases when close goes up", () => {
    const result = obv(close, volume);
    // close[1] > close[0] → OBV[1] > OBV[0]
    expect(result[1]).toBeGreaterThan(result[0]);
  });
});

describe("Heikin-Ashi", () => {
  it("output has same length as input", () => {
    const bars = close.map((c, i) => ({ open: c - 0.5, high: high[i], low: low[i], close: c }));
    const result = heikinAshi(bars);
    expect(result.length).toBe(bars.length);
  });

  it("HA close = average of OHLC", () => {
    const bars = [{ open: 100, high: 105, low: 98, close: 103 }];
    const result = heikinAshi(bars);
    expect(result[0].close).toBeCloseTo((100 + 105 + 98 + 103) / 4, 4);
  });
});
import {
  stochasticRsi,
  cci,
  williamsR,
  parabolicSar,
  donchianChannel,
  keltnerChannel,
} from "@/lib/indicators";

// Extended dataset for new indicators (50 bars)
const close50 = Array.from({ length: 50 }, (_, i) => 100 + Math.sin(i * 0.3) * 10 + i * 0.5);
const high50 = close50.map((c) => c + 2);
const low50 = close50.map((c) => c - 2);

describe("Stochastic RSI", () => {
  it("returns arrays of same length as input", () => {
    const result = stochasticRsi(close50, high50, low50, 14, 3, 3);
    expect(result.k.length).toBe(close50.length);
    expect(result.d.length).toBe(close50.length);
  });

  it("k and d values are in 0–100 range where defined", () => {
    const result = stochasticRsi(close50, high50, low50, 14, 3, 3);
    for (const v of result.k) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
    for (const v of result.d) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
  });
});

describe("CCI", () => {
  it("returns NaN before period-1 index", () => {
    const result = cci(high50, low50, close50, 20);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[18])).toBe(true);
  });

  it("returns a finite value at period-1 index", () => {
    const result = cci(high50, low50, close50, 20);
    expect(isFinite(result[19])).toBe(true);
  });
});

describe("Williams %R", () => {
  it("all defined values are in [−100, 0] range", () => {
    const result = williamsR(high50, low50, close50, 14);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(-100);
        expect(v).toBeLessThanOrEqual(0);
      }
    }
  });

  it("equals −100 when close is at the lowest low", () => {
    // constant high, constant low — close equals low → %R = -100
    const highs = [10, 10, 10];
    const lows = [5, 5, 5];
    const closes = [5, 5, 5];
    const result = williamsR(highs, lows, closes, 3);
    expect(result[2]).toBeCloseTo(-100, 4);
  });
});

describe("Parabolic SAR", () => {
  it("returns same length array as input", () => {
    const result = parabolicSar(high50, low50, 0.02, 0.2);
    expect(result.length).toBe(high50.length);
  });

  it("all values are finite numbers", () => {
    const result = parabolicSar(high50, low50, 0.02, 0.2);
    for (const v of result) {
      expect(isFinite(v)).toBe(true);
    }
  });
});

describe("Donchian Channel", () => {
  it("upper >= lower for all valid values", () => {
    const result = donchianChannel(high50, low50, 20);
    for (let i = 19; i < high50.length; i++) {
      expect(result.upper[i]).toBeGreaterThanOrEqual(result.lower[i]);
    }
  });

  it("mid = (upper + lower) / 2", () => {
    const result = donchianChannel(high50, low50, 5);
    for (let i = 4; i < high50.length; i++) {
      expect(result.mid[i]).toBeCloseTo((result.upper[i] + result.lower[i]) / 2, 6);
    }
  });
});

describe("Keltner Channel", () => {
  it("upper > mid > lower for all valid values", () => {
    const result = keltnerChannel(high50, low50, close50, 14, 2);
    for (let i = 0; i < close50.length; i++) {
      if (!isNaN(result.upper[i])) {
        expect(result.upper[i]).toBeGreaterThan(result.mid[i]);
        expect(result.mid[i]).toBeGreaterThan(result.lower[i]);
      }
    }
  });

  it("returns arrays of same length as input", () => {
    const result = keltnerChannel(high50, low50, close50, 14, 2);
    expect(result.upper.length).toBe(close50.length);
    expect(result.mid.length).toBe(close50.length);
    expect(result.lower.length).toBe(close50.length);
  });
});

// ─── Sprint 7 ST-AC: Extended indicator tests ─────────────────────────────────
import {
  ichimokuCloud,
  superTrend,
  trix,
  roc,
  ultimateOscillator,
} from "@/lib/indicators";

// Use 60-bar dataset for indicators requiring longer history
const close60 = Array.from({ length: 60 }, (_, i) => 100 + Math.sin(i * 0.25) * 15 + i * 0.3);
const high60 = close60.map((c) => c + 2);
const low60 = close60.map((c) => c - 2);

describe("Ichimoku Cloud", () => {
  it("returns all 5 components with same length as input", () => {
    const result = ichimokuCloud(high60, low60, close60, 9, 26, 52, 26);
    expect(result.tenkan.length).toBe(close60.length);
    expect(result.kijun.length).toBe(close60.length);
    expect(result.senkouA.length).toBe(close60.length);
    expect(result.senkouB.length).toBe(close60.length);
    expect(result.chikou.length).toBe(close60.length);
  });

  it("tenkan is NaN before tenkanPeriod-1 and defined at tenkanPeriod-1", () => {
    const result = ichimokuCloud(high60, low60, close60, 9, 26, 52, 26);
    expect(isNaN(result.tenkan[0])).toBe(true);
    expect(isNaN(result.tenkan[7])).toBe(true);
    expect(isFinite(result.tenkan[8])).toBe(true);
  });
});

describe("SuperTrend", () => {
  it("returns values and direction arrays of same length as input", () => {
    const result = superTrend(high60, low60, close60, 10, 3);
    expect(result.values.length).toBe(close60.length);
    expect(result.direction.length).toBe(close60.length);
  });

  it("direction values are either 1 or -1 where defined", () => {
    const result = superTrend(high60, low60, close60, 10, 3);
    for (const d of result.direction) {
      if (!isNaN(d)) {
        expect([1, -1]).toContain(d);
      }
    }
  });
});

describe("TRIX", () => {
  it("returns array of same length as input", () => {
    const result = trix(close60, 5);
    expect(result.length).toBe(close60.length);
  });

  it("first valid value is a finite number", () => {
    const result = trix(close60, 5);
    const firstValid = result.find((v) => !isNaN(v));
    expect(firstValid).toBeDefined();
    expect(isFinite(firstValid!)).toBe(true);
  });
});

describe("ROC", () => {
  it("returns NaN before period index", () => {
    const result = roc(close60, 12);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[11])).toBe(true);
  });

  it("computes correct ROC at period index", () => {
    const prices = [100, 110, 120, 130, 140, 150];
    const result = roc(prices, 3);
    // ROC[3] = (130 - 100) / 100 * 100 = 30
    expect(result[3]).toBeCloseTo(30, 4);
  });
});

describe("Ultimate Oscillator", () => {
  it("returns array of same length as input", () => {
    const result = ultimateOscillator(high60, low60, close60, 7, 14, 28);
    expect(result.length).toBe(close60.length);
  });

  it("all defined values are in 0–100 range", () => {
    const result = ultimateOscillator(high60, low60, close60, 7, 14, 28);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
  });
});

import {
  accumulationDistribution,
  cmf,
  mfi,
  forceIndex,
  rvol,
  pivotPoints,
} from "@/lib/indicators";

const vol50 = Array.from({ length: 50 }, () => 1_000_000);

describe("Accumulation/Distribution", () => {
  it("returns array of same length as input", () => {
    const result = accumulationDistribution(high50, low50, close50, vol50);
    expect(result.length).toBe(close50.length);
  });

  it("starts at CLV * volume of first bar (no NaN)", () => {
    const result = accumulationDistribution(high50, low50, close50, vol50);
    expect(isNaN(result[0])).toBe(false);
  });

  it("is cumulative — value increases when CLV > 0 with bullish bar", () => {
    // constant high=11, low=9, close=11 → CLV = ((11-9)-(11-11))/(11-9) = 1 → AD increases
    const h = [11, 11, 11];
    const l = [9, 9, 9];
    const c = [11, 11, 11];
    const v = [1000, 1000, 1000];
    const result = accumulationDistribution(h, l, c, v);
    expect(result[1]).toBeGreaterThan(result[0]);
  });
});

describe("CMF", () => {
  it("returns NaN before period-1 index", () => {
    const result = cmf(high50, low50, close50, vol50, 20);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[18])).toBe(true);
  });

  it("values are in [-1, 1] range for valid entries", () => {
    const result = cmf(high50, low50, close50, vol50, 10);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(-1);
        expect(v).toBeLessThanOrEqual(1);
      }
    }
  });
});

describe("MFI", () => {
  it("returns NaN before enough data", () => {
    const result = mfi(high50, low50, close50, vol50, 14);
    expect(isNaN(result[0])).toBe(true);
  });

  it("values are in [0, 100] range for valid entries", () => {
    const result = mfi(high50, low50, close50, vol50, 14);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
  });
});

describe("Force Index", () => {
  it("returns NaN at index 0", () => {
    const result = forceIndex(close50, vol50, 13);
    expect(isNaN(result[0])).toBe(true);
  });

  it("returns same-length array as input", () => {
    const result = forceIndex(close50, vol50, 13);
    expect(result.length).toBe(close50.length);
  });
});

describe("RVOL", () => {
  it("returns NaN before period-1 index", () => {
    const result = rvol(vol50, 20);
    expect(isNaN(result[0])).toBe(true);
    expect(isNaN(result[18])).toBe(true);
  });

  it("returns ~1 when volume is constant (equals SMA of same constant)", () => {
    const constVol = Array.from({ length: 30 }, () => 5000);
    const result = rvol(constVol, 10);
    for (const v of result) {
      if (!isNaN(v)) {
        expect(v).toBeCloseTo(1, 5);
      }
    }
  });
});

describe("Pivot Points", () => {
  it("first bar has NaN for all levels", () => {
    const result = pivotPoints(high50, low50, close50);
    expect(isNaN(result.P[0])).toBe(true);
    expect(isNaN(result.R1[0])).toBe(true);
    expect(isNaN(result.S1[0])).toBe(true);
  });

  it("R1 > P > S1 for valid bars", () => {
    const result = pivotPoints(high50, low50, close50);
    for (let i = 1; i < close50.length; i++) {
      expect(result.R1[i]).toBeGreaterThan(result.P[i]);
      expect(result.P[i]).toBeGreaterThan(result.S1[i]);
    }
  });
});
