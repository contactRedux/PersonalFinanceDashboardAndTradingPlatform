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
