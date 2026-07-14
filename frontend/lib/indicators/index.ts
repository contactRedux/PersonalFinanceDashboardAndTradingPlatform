/**
 * Technical indicator compute functions — pure TypeScript, no side effects.
 *
 * All functions accept numeric arrays (close, high, low, volume) and return
 * result arrays of the same or shorter length. NaN is used for "no value" at
 * the start of arrays before the indicator has enough data.
 *
 * These mirror the TA-Lib computations on the server side but run client-side
 * for real-time chart overlay rendering.
 */

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function sma(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  for (let i = period - 1; i < values.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    result[i] = sum / period;
  }
  return result;
}

export function ema(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  const k = 2 / (period + 1);
  let prevEma: number | undefined;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) continue;
    if (prevEma === undefined) {
      // Seed with SMA
      let sum = 0;
      for (let j = 0; j < period; j++) sum += values[i - j];
      prevEma = sum / period;
    } else {
      prevEma = values[i] * k + prevEma * (1 - k);
    }
    result[i] = prevEma;
  }
  return result;
}

export function wma(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  const denom = (period * (period + 1)) / 2;
  for (let i = period - 1; i < values.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += values[i - j] * (period - j);
    }
    result[i] = sum / denom;
  }
  return result;
}

export function dema(values: number[], period: number): number[] {
  const e1 = ema(values, period);
  const e2 = ema(e1.filter((v) => !isNaN(v)), period);
  const result: number[] = new Array(values.length).fill(NaN);
  let e2Idx = 0;
  for (let i = period - 1; i < values.length; i++) {
    if (e2Idx < e2.length && !isNaN(e2[e2Idx])) {
      result[i] = 2 * e1[i] - e2[e2Idx];
      e2Idx++;
    }
  }
  return result;
}

export function tema(values: number[], period: number): number[] {
  const e1 = ema(values, period);
  const nonNanE1 = e1.filter((v) => !isNaN(v));
  const e2 = ema(nonNanE1, period);
  const nonNanE2 = e2.filter((v) => !isNaN(v));
  const e3 = ema(nonNanE2, period);
  const result: number[] = new Array(values.length).fill(NaN);
  const offset = values.length - e3.filter((v) => !isNaN(v)).length;
  for (let i = offset; i < values.length; i++) {
    const idx = i - offset;
    const e1v = e1[i];
    const e2v = e2[idx] ?? NaN;
    const e3v = e3[idx - (nonNanE1.length - e3.filter((v) => !isNaN(v)).length)] ?? NaN;
    if (!isNaN(e1v) && !isNaN(e2v) && !isNaN(e3v)) {
      result[i] = 3 * e1v - 3 * e2v + e3v;
    }
  }
  return result;
}

/** Hull Moving Average */
export function hma(values: number[], period: number): number[] {
  const halfPeriod = Math.floor(period / 2);
  const sqrtPeriod = Math.round(Math.sqrt(period));
  const wma1 = wma(values, halfPeriod);
  const wma2 = wma(values, period);
  const diff = wma1.map((v, i) => (isNaN(v) || isNaN(wma2[i]) ? NaN : 2 * v - wma2[i]));
  return wma(
    diff.filter((v) => !isNaN(v)),
    sqrtPeriod
  ).map((v, i) => (i < sqrtPeriod - 1 ? NaN : v));
}

// ─── Momentum ─────────────────────────────────────────────────────────────────

export interface MACDResult {
  macd: number[];
  signal: number[];
  histogram: number[];
}

export function macd(
  close: number[],
  fastPeriod = 12,
  slowPeriod = 26,
  signalPeriod = 9
): MACDResult {
  const fastEma = ema(close, fastPeriod);
  const slowEma = ema(close, slowPeriod);
  const macdLine = fastEma.map((v, i) =>
    isNaN(v) || isNaN(slowEma[i]) ? NaN : v - slowEma[i]
  );
  const signalLine = ema(
    macdLine.filter((v) => !isNaN(v)),
    signalPeriod
  );
  const result: MACDResult = {
    macd: macdLine,
    signal: new Array(close.length).fill(NaN),
    histogram: new Array(close.length).fill(NaN),
  };
  let sIdx = 0;
  for (let i = 0; i < close.length; i++) {
    if (!isNaN(macdLine[i]) && sIdx < signalLine.length && !isNaN(signalLine[sIdx])) {
      result.signal[i] = signalLine[sIdx];
      result.histogram[i] = macdLine[i] - signalLine[sIdx];
      sIdx++;
    }
  }
  return result;
}

export function rsi(close: number[], period = 14): number[] {
  const result: number[] = new Array(close.length).fill(NaN);
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const change = close[i] - close[i - 1];
    if (change > 0) avgGain += change;
    else avgLoss += Math.abs(change);
  }
  avgGain /= period;
  avgLoss /= period;
  if (avgLoss === 0) {
    result[period] = 100;
  } else {
    result[period] = 100 - 100 / (1 + avgGain / avgLoss);
  }
  for (let i = period + 1; i < close.length; i++) {
    const change = close[i] - close[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    if (avgLoss === 0) {
      result[i] = 100;
    } else {
      result[i] = 100 - 100 / (1 + avgGain / avgLoss);
    }
  }
  return result;
}

// ─── Volatility ───────────────────────────────────────────────────────────────

export interface BollingerBandsResult {
  upper: number[];
  middle: number[];
  lower: number[];
}

export function bollingerBands(
  close: number[],
  period = 20,
  stdDevMult = 2
): BollingerBandsResult {
  const middle = sma(close, period);
  const upper: number[] = new Array(close.length).fill(NaN);
  const lower: number[] = new Array(close.length).fill(NaN);
  for (let i = period - 1; i < close.length; i++) {
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumSq += (close[j] - middle[i]) ** 2;
    }
    const stdDev = Math.sqrt(sumSq / period);
    upper[i] = middle[i] + stdDevMult * stdDev;
    lower[i] = middle[i] - stdDevMult * stdDev;
  }
  return { upper, middle, lower };
}

export function atr(
  high: number[],
  low: number[],
  close: number[],
  period = 14
): number[] {
  const result: number[] = new Array(close.length).fill(NaN);
  const trueRanges: number[] = [NaN];
  for (let i = 1; i < close.length; i++) {
    const hl = high[i] - low[i];
    const hpc = Math.abs(high[i] - close[i - 1]);
    const lpc = Math.abs(low[i] - close[i - 1]);
    trueRanges.push(Math.max(hl, hpc, lpc));
  }
  // Initial ATR = SMA of first `period` true ranges
  if (trueRanges.length > period) {
    let sum = 0;
    for (let i = 1; i <= period; i++) sum += trueRanges[i];
    let prevATR = sum / period;
    result[period] = prevATR;
    for (let i = period + 1; i < close.length; i++) {
      prevATR = (prevATR * (period - 1) + trueRanges[i]) / period;
      result[i] = prevATR;
    }
  }
  return result;
}

// ─── Volume ───────────────────────────────────────────────────────────────────

export function vwap(
  high: number[],
  low: number[],
  close: number[],
  volume: number[]
): number[] {
  const result: number[] = new Array(close.length).fill(NaN);
  let cumTPV = 0;
  let cumVol = 0;
  for (let i = 0; i < close.length; i++) {
    const typicalPrice = (high[i] + low[i] + close[i]) / 3;
    cumTPV += typicalPrice * volume[i];
    cumVol += volume[i];
    result[i] = cumVol > 0 ? cumTPV / cumVol : NaN;
  }
  return result;
}

export function obv(close: number[], volume: number[]): number[] {
  const result: number[] = [volume[0] ?? 0];
  for (let i = 1; i < close.length; i++) {
    if (close[i] > close[i - 1]) result.push(result[i - 1] + volume[i]);
    else if (close[i] < close[i - 1]) result.push(result[i - 1] - volume[i]);
    else result.push(result[i - 1]);
  }
  return result;
}

// ─── Heikin-Ashi transform ────────────────────────────────────────────────────

export interface OHLCBar {
  open: number;
  high: number;
  low: number;
  close: number;
}

export function heikinAshi(bars: OHLCBar[]): OHLCBar[] {
  const result: OHLCBar[] = [];
  for (let i = 0; i < bars.length; i++) {
    const haClose = (bars[i].open + bars[i].high + bars[i].low + bars[i].close) / 4;
    const haOpen =
      i === 0
        ? (bars[i].open + bars[i].close) / 2
        : (result[i - 1].open + result[i - 1].close) / 2;
    const haHigh = Math.max(bars[i].high, haOpen, haClose);
    const haLow = Math.min(bars[i].low, haOpen, haClose);
    result.push({ open: haOpen, high: haHigh, low: haLow, close: haClose });
  }
  return result;
}
