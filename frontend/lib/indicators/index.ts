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

// ─── Momentum + Trend (ST-V indicators) ─────────────────────────────────────

export interface StochasticRsiResult {
  k: number[];
  d: number[];
}

/**
 * Stochastic RSI — RSI of RSI, smoothed with two SMAs.
 * Returns k and d arrays of the same length as `closes` (NaN before enough data).
 */
export function stochasticRsi(
  closes: number[],
  _highs: number[],
  _lows: number[],
  period: number,
  smoothK: number,
  smoothD: number
): StochasticRsiResult {
  const rsiValues = rsi(closes, period);
  const n = closes.length;
  const rawK: number[] = new Array(n).fill(NaN);

  for (let i = period * 2 - 2; i < n; i++) {
    let minRsi = Infinity;
    let maxRsi = -Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (!isNaN(rsiValues[j])) {
        if (rsiValues[j] < minRsi) minRsi = rsiValues[j];
        if (rsiValues[j] > maxRsi) maxRsi = rsiValues[j];
      }
    }
    const range = maxRsi - minRsi;
    rawK[i] = range === 0 ? 0 : ((rsiValues[i] - minRsi) / range) * 100;
  }

  const kLine = sma(rawK.filter((v) => !isNaN(v)), smoothK);
  const dLine = sma(kLine.filter((v) => !isNaN(v)), smoothD);

  const k: number[] = new Array(n).fill(NaN);
  const d: number[] = new Array(n).fill(NaN);
  let kIdx = 0;
  for (let i = 0; i < n; i++) {
    if (!isNaN(rawK[i]) && kIdx < kLine.length && !isNaN(kLine[kIdx])) {
      k[i] = kLine[kIdx];
      kIdx++;
    }
  }
  let dIdx = 0;
  for (let i = 0; i < n; i++) {
    if (!isNaN(k[i]) && dIdx < dLine.length && !isNaN(dLine[dIdx])) {
      d[i] = dLine[dIdx];
      dIdx++;
    }
  }
  return { k, d };
}

/**
 * CCI — (Typical Price − SMA of TP) / (0.015 × Mean Deviation).
 */
export function cci(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  for (let i = period - 1; i < n; i++) {
    let sumTP = 0;
    const tps: number[] = [];
    for (let j = i - period + 1; j <= i; j++) {
      const tp = (highs[j] + lows[j] + closes[j]) / 3;
      tps.push(tp);
      sumTP += tp;
    }
    const meanTP = sumTP / period;
    let meanDev = 0;
    for (const tp of tps) meanDev += Math.abs(tp - meanTP);
    meanDev /= period;
    result[i] = meanDev === 0 ? 0 : (tps[tps.length - 1] - meanTP) / (0.015 * meanDev);
  }
  return result;
}

/**
 * Williams %R — (Highest High − Close) / (Highest High − Lowest Low) × −100.
 */
export function williamsR(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  for (let i = period - 1; i < n; i++) {
    let hh = -Infinity;
    let ll = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (highs[j] > hh) hh = highs[j];
      if (lows[j] < ll) ll = lows[j];
    }
    const range = hh - ll;
    result[i] = range === 0 ? -50 : ((hh - closes[i]) / range) * -100;
  }
  return result;
}

/**
 * Parabolic SAR — standard Wilder SAR.
 */
export function parabolicSar(
  highs: number[],
  lows: number[],
  step: number,
  max: number
): number[] {
  const n = highs.length;
  if (n < 2) return new Array(n).fill(NaN);

  const result: number[] = new Array(n).fill(NaN);
  let isLong = true;
  let sar = lows[0];
  let ep = highs[0];
  let af = step;

  result[0] = sar;

  for (let i = 1; i < n; i++) {
    const prevSar = sar;

    if (isLong) {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.min(sar, lows[i - 1], i >= 2 ? lows[i - 2] : lows[i - 1]);

      if (highs[i] > ep) {
        ep = highs[i];
        af = Math.min(af + step, max);
      }

      if (lows[i] < sar) {
        // Reverse to short
        isLong = false;
        sar = ep;
        ep = lows[i];
        af = step;
      }
    } else {
      sar = prevSar + af * (ep - prevSar);
      sar = Math.max(sar, highs[i - 1], i >= 2 ? highs[i - 2] : highs[i - 1]);

      if (lows[i] < ep) {
        ep = lows[i];
        af = Math.min(af + step, max);
      }

      if (highs[i] > sar) {
        // Reverse to long
        isLong = true;
        sar = ep;
        ep = highs[i];
        af = step;
      }
    }

    result[i] = sar;
  }
  return result;
}

export interface DonchianChannelResult {
  upper: number[];
  lower: number[];
  mid: number[];
}

/**
 * Donchian Channel — rolling max high / min low, mid = (upper + lower) / 2.
 */
export function donchianChannel(
  highs: number[],
  lows: number[],
  period: number
): DonchianChannelResult {
  const n = highs.length;
  const upper: number[] = new Array(n).fill(NaN);
  const lower: number[] = new Array(n).fill(NaN);
  const mid: number[] = new Array(n).fill(NaN);
  for (let i = period - 1; i < n; i++) {
    let maxH = -Infinity;
    let minL = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (highs[j] > maxH) maxH = highs[j];
      if (lows[j] < minL) minL = lows[j];
    }
    upper[i] = maxH;
    lower[i] = minL;
    mid[i] = (maxH + minL) / 2;
  }
  return { upper, lower, mid };
}

export interface KeltnerChannelResult {
  upper: number[];
  mid: number[];
  lower: number[];
}

/**
 * Keltner Channel — EMA ± multiplier × ATR.
 */
export function keltnerChannel(
  highs: number[],
  lows: number[],
  closes: number[],
  atrPeriod: number,
  multiplier: number
): KeltnerChannelResult {
  const midLine = ema(closes, atrPeriod);
  const atrValues = atr(highs, lows, closes, atrPeriod);
  const n = closes.length;
  const upper: number[] = new Array(n).fill(NaN);
  const mid: number[] = new Array(n).fill(NaN);
  const lower: number[] = new Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    if (!isNaN(midLine[i]) && !isNaN(atrValues[i])) {
      mid[i] = midLine[i];
      upper[i] = midLine[i] + multiplier * atrValues[i];
      lower[i] = midLine[i] - multiplier * atrValues[i];
    }
  }
  return { upper, mid, lower };
}

// ─── Extended Indicators (Sprint 7 ST-AC) ─────────────────────────────────────

export interface IchimokuCloudResult {
  tenkan: number[];
  kijun: number[];
  senkouA: number[];
  senkouB: number[];
  chikou: number[];
}

/** Rolling max of an array over a lookback window (helper). */
function rollingMax(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  for (let i = period - 1; i < values.length; i++) {
    let max = -Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (values[j] > max) max = values[j];
    }
    result[i] = max;
  }
  return result;
}

/** Rolling min of an array over a lookback window (helper). */
function rollingMin(values: number[], period: number): number[] {
  const result: number[] = new Array(values.length).fill(NaN);
  for (let i = period - 1; i < values.length; i++) {
    let min = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (values[j] < min) min = values[j];
    }
    result[i] = min;
  }
  return result;
}

/**
 * Ichimoku Cloud
 * - tenkan-sen:  (max(high, tenkanPeriod)  + min(low, tenkanPeriod))  / 2
 * - kijun-sen:   (max(high, kijunPeriod)   + min(low, kijunPeriod))   / 2
 * - senkou A:    (tenkan + kijun) / 2, displaced forward by `displacement` bars
 * - senkou B:    (max(high, senkouBPeriod) + min(low, senkouBPeriod)) / 2, displaced forward
 * - chikou:      close shifted back by `displacement` bars
 */
export function ichimokuCloud(
  highs: number[],
  lows: number[],
  closes: number[],
  tenkanPeriod = 9,
  kijunPeriod = 26,
  senkouBPeriod = 52,
  displacement = 26
): IchimokuCloudResult {
  const n = closes.length;
  const total = n + displacement;

  const maxHigh = rollingMax(highs, tenkanPeriod);
  const minLow = rollingMin(lows, tenkanPeriod);
  const maxHighK = rollingMax(highs, kijunPeriod);
  const minLowK = rollingMin(lows, kijunPeriod);
  const maxHighB = rollingMax(highs, senkouBPeriod);
  const minLowB = rollingMin(lows, senkouBPeriod);

  const tenkan: number[] = new Array(n).fill(NaN);
  const kijun: number[] = new Array(n).fill(NaN);
  const senkouA: number[] = new Array(total).fill(NaN);
  const senkouB: number[] = new Array(total).fill(NaN);
  const chikou: number[] = new Array(n).fill(NaN);

  for (let i = 0; i < n; i++) {
    if (!isNaN(maxHigh[i]) && !isNaN(minLow[i])) {
      tenkan[i] = (maxHigh[i] + minLow[i]) / 2;
    }
    if (!isNaN(maxHighK[i]) && !isNaN(minLowK[i])) {
      kijun[i] = (maxHighK[i] + minLowK[i]) / 2;
    }
    // Senkou A & B displaced forward
    if (!isNaN(tenkan[i]) && !isNaN(kijun[i])) {
      senkouA[i + displacement] = (tenkan[i] + kijun[i]) / 2;
    }
    if (!isNaN(maxHighB[i]) && !isNaN(minLowB[i])) {
      senkouB[i + displacement] = (maxHighB[i] + minLowB[i]) / 2;
    }
    // Chikou: close shifted back by displacement
    if (i - displacement >= 0) {
      chikou[i - displacement] = closes[i];
    }
  }

  return { tenkan, kijun, senkouA: senkouA.slice(0, n), senkouB: senkouB.slice(0, n), chikou };
}

export interface SuperTrendResult {
  values: number[];
  direction: number[]; // 1 = uptrend, -1 = downtrend
}

/**
 * SuperTrend
 * - upperBand = ((high+low)/2) + multiplier*ATR
 * - lowerBand = ((high+low)/2) - multiplier*ATR
 * - direction: 1 = uptrend (green), -1 = downtrend (red)
 */
export function superTrend(
  highs: number[],
  lows: number[],
  closes: number[],
  period = 10,
  multiplier = 3
): SuperTrendResult {
  const n = closes.length;
  const atrValues = atr(highs, lows, closes, period);
  const values: number[] = new Array(n).fill(NaN);
  const direction: number[] = new Array(n).fill(NaN);

  let upperBand = NaN;
  let lowerBand = NaN;
  let prevUpperBand = NaN;
  let prevLowerBand = NaN;
  let prevDir = 1;

  for (let i = period; i < n; i++) {
    if (isNaN(atrValues[i])) continue;
    const hl2 = (highs[i] + lows[i]) / 2;
    const rawUpper = hl2 + multiplier * atrValues[i];
    const rawLower = hl2 - multiplier * atrValues[i];

    // Final upper band: lock in tighter of new/prev
    upperBand = (rawUpper < prevUpperBand || closes[i - 1] > prevUpperBand) ? rawUpper : prevUpperBand;
    // Final lower band: lock in higher of new/prev
    lowerBand = (rawLower > prevLowerBand || closes[i - 1] < prevLowerBand) ? rawLower : prevLowerBand;

    let dir: number;
    if (closes[i] <= upperBand) {
      dir = -1;
    } else {
      dir = 1;
    }
    if (prevDir === -1 && closes[i] > prevUpperBand) dir = 1;
    if (prevDir === 1 && closes[i] < prevLowerBand) dir = -1;

    values[i] = dir === 1 ? lowerBand : upperBand;
    direction[i] = dir;
    prevUpperBand = upperBand;
    prevLowerBand = lowerBand;
    prevDir = dir;
  }

  return { values, direction };
}

/**
 * TRIX — triple-smoothed EMA, then 1-period Rate of Change.
 * Returns percentage change of triple-EMA.
 */
export function trix(closes: number[], period: number): number[] {
  const n = closes.length;
  const e1 = ema(closes, period);
  const validE1 = e1.filter((v) => !isNaN(v));
  const e2 = ema(validE1, period);
  const validE2 = e2.filter((v) => !isNaN(v));
  const e3 = ema(validE2, period);

  // Map e3 back into the original array length
  const result: number[] = new Array(n).fill(NaN);
  // e3 has validE2.length entries, aligned to the tail of the original array
  const e3StartInN = n - e3.length;
  for (let i = 1; i < e3.length; i++) {
    if (!isNaN(e3[i]) && !isNaN(e3[i - 1]) && e3[i - 1] !== 0) {
      result[e3StartInN + i] = ((e3[i] - e3[i - 1]) / e3[i - 1]) * 100;
    }
  }
  return result;
}

/**
 * Rate of Change (ROC)
 * ROC[i] = (close[i] - close[i-period]) / close[i-period] * 100
 */
export function roc(closes: number[], period: number): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  for (let i = period; i < n; i++) {
    if (closes[i - period] !== 0) {
      result[i] = ((closes[i] - closes[i - period]) / closes[i - period]) * 100;
    }
  }
  return result;
}

/**
 * Ultimate Oscillator
 * Buying pressure (BP) = close - min(low, prev_close)
 * True range (TR) = max(high, prev_close) - min(low, prev_close)
 * Weighted average over 3 periods with 4:2:1 ratio
 */
export function ultimateOscillator(
  highs: number[],
  lows: number[],
  closes: number[],
  period1 = 7,
  period2 = 14,
  period3 = 28
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);

  const bp: number[] = new Array(n).fill(NaN);
  const tr: number[] = new Array(n).fill(NaN);

  for (let i = 1; i < n; i++) {
    const prevClose = closes[i - 1];
    const trueHigh = Math.max(highs[i], prevClose);
    const trueLow = Math.min(lows[i], prevClose);
    bp[i] = closes[i] - trueLow;
    tr[i] = trueHigh - trueLow;
  }

  const minPeriod = Math.max(period1, period2, period3);
  for (let i = minPeriod; i < n; i++) {
    let sumBP1 = 0, sumTR1 = 0;
    let sumBP2 = 0, sumTR2 = 0;
    let sumBP3 = 0, sumTR3 = 0;
    for (let j = i - period1 + 1; j <= i; j++) { sumBP1 += bp[j]; sumTR1 += tr[j]; }
    for (let j = i - period2 + 1; j <= i; j++) { sumBP2 += bp[j]; sumTR2 += tr[j]; }
    for (let j = i - period3 + 1; j <= i; j++) { sumBP3 += bp[j]; sumTR3 += tr[j]; }
    if (sumTR1 === 0 || sumTR2 === 0 || sumTR3 === 0) continue;
    const avg1 = sumBP1 / sumTR1;
    const avg2 = sumBP2 / sumTR2;
    const avg3 = sumBP3 / sumTR3;
    result[i] = (100 * (4 * avg1 + 2 * avg2 + avg3)) / 7;
  }
  return result;
}

// ─── Volume & Structure (ST-W indicators) ────────────────────────────────────

/**
 * Accumulation/Distribution Line.
 * CLV = ((close - low) - (high - close)) / (high - low)
 * AD[i] = AD[i-1] + CLV[i] * volume[i]
 */
export function accumulationDistribution(
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[]
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  let ad = 0;
  for (let i = 0; i < n; i++) {
    const hl = highs[i] - lows[i];
    const clv = hl === 0 ? 0 : ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl;
    ad += clv * volumes[i];
    result[i] = ad;
  }
  return result;
}

/**
 * Chaikin Money Flow — sum(CLV*vol, period) / sum(vol, period).
 */
export function cmf(
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[],
  period: number
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  for (let i = period - 1; i < n; i++) {
    let sumClvVol = 0;
    let sumVol = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const hl = highs[j] - lows[j];
      const clv = hl === 0 ? 0 : ((closes[j] - lows[j]) - (highs[j] - closes[j])) / hl;
      sumClvVol += clv * volumes[j];
      sumVol += volumes[j];
    }
    result[i] = sumVol === 0 ? 0 : sumClvVol / sumVol;
  }
  return result;
}

/**
 * Money Flow Index — 100 - (100 / (1 + positive_mf / negative_mf)).
 */
export function mfi(
  highs: number[],
  lows: number[],
  closes: number[],
  volumes: number[],
  period: number
): number[] {
  const n = closes.length;
  const result: number[] = new Array(n).fill(NaN);
  const typicalPrices = closes.map((c, i) => (highs[i] + lows[i] + c) / 3);
  const rawMF = typicalPrices.map((tp, i) => tp * volumes[i]);

  for (let i = period; i < n; i++) {
    let posMF = 0;
    let negMF = 0;
    for (let j = i - period + 1; j <= i; j++) {
      if (typicalPrices[j] > typicalPrices[j - 1]) {
        posMF += rawMF[j];
      } else if (typicalPrices[j] < typicalPrices[j - 1]) {
        negMF += rawMF[j];
      }
    }
    if (negMF === 0) {
      result[i] = 100;
    } else {
      result[i] = 100 - 100 / (1 + posMF / negMF);
    }
  }
  return result;
}

/**
 * Force Index — EMA of (close[i] - close[i-1]) * volume[i].
 */
export function forceIndex(
  closes: number[],
  volumes: number[],
  period: number
): number[] {
  const n = closes.length;
  const rawFI: number[] = new Array(n).fill(NaN);
  for (let i = 1; i < n; i++) {
    rawFI[i] = (closes[i] - closes[i - 1]) * volumes[i];
  }
  // EMA of rawFI values starting from index 1
  const validFI = rawFI.slice(1);
  const emaFI = ema(validFI, period);
  const result: number[] = new Array(n).fill(NaN);
  for (let i = 0; i < emaFI.length; i++) {
    result[i + 1] = emaFI[i];
  }
  return result;
}

/**
 * Relative Volume — volume[i] / SMA(volume, period)[i].
 */
export function rvol(volumes: number[], period: number): number[] {
  const smaVol = sma(volumes, period);
  return volumes.map((v, i) =>
    isNaN(smaVol[i]) || smaVol[i] === 0 ? NaN : v / smaVol[i]
  );
}

export interface PivotPointsResult {
  P: number[];
  R1: number[];
  R2: number[];
  R3: number[];
  S1: number[];
  S2: number[];
  S3: number[];
}

/**
 * Standard floor pivot points.
 * Each bar's pivot is computed from the previous bar's H, L, C.
 * First bar has NaN for all levels.
 */
export function pivotPoints(
  highs: number[],
  lows: number[],
  closes: number[]
): PivotPointsResult {
  const n = closes.length;
  const P: number[] = new Array(n).fill(NaN);
  const R1: number[] = new Array(n).fill(NaN);
  const R2: number[] = new Array(n).fill(NaN);
  const R3: number[] = new Array(n).fill(NaN);
  const S1: number[] = new Array(n).fill(NaN);
  const S2: number[] = new Array(n).fill(NaN);
  const S3: number[] = new Array(n).fill(NaN);

  for (let i = 1; i < n; i++) {
    const H = highs[i - 1];
    const L = lows[i - 1];
    const C = closes[i - 1];
    const p = (H + L + C) / 3;
    P[i] = p;
    R1[i] = 2 * p - L;
    S1[i] = 2 * p - H;
    R2[i] = p + (H - L);
    S2[i] = p - (H - L);
    R3[i] = H + 2 * (p - L);
    S3[i] = L - 2 * (H - p);
  }

  return { P, R1, R2, R3, S1, S2, S3 };
}
