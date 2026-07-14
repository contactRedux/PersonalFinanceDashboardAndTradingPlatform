"""
Extended technical indicator implementations — pure Python, no dependencies.

Sprint 7 ST-AC: Ichimoku Cloud, SuperTrend, TRIX, ROC, Ultimate Oscillator.
These mirror the TypeScript implementations in frontend/lib/indicators/index.ts.
"""

from __future__ import annotations

import math
from typing import NamedTuple


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _rolling_max(values: list[float], period: int) -> list[float]:
    n = len(values)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        result[i] = max(values[i - period + 1 : i + 1])
    return result


def _rolling_min(values: list[float], period: int) -> list[float]:
    n = len(values)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        result[i] = min(values[i - period + 1 : i + 1])
    return result


def _ema(values: list[float], period: int) -> list[float]:
    n = len(values)
    result = [float("nan")] * n
    k = 2.0 / (period + 1)
    prev: float | None = None
    for i in range(n):
        if i < period - 1:
            continue
        if prev is None:
            prev = sum(values[i - period + 1 : i + 1]) / period
        else:
            prev = values[i] * k + prev * (1 - k)
        result[i] = prev
    return result


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    n = len(closes)
    result = [float("nan")] * n
    trs: list[float] = [float("nan")]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hpc = abs(highs[i] - closes[i - 1])
        lpc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hpc, lpc))
    if len(trs) > period:
        prev_atr = sum(trs[1 : period + 1]) / period
        result[period] = prev_atr
        for i in range(period + 1, n):
            prev_atr = (prev_atr * (period - 1) + trs[i]) / period
            result[i] = prev_atr
    return result


# ─── Ichimoku Cloud ───────────────────────────────────────────────────────────


class IchimokuCloudResult(NamedTuple):
    tenkan: list[float]
    kijun: list[float]
    senkou_a: list[float]
    senkou_b: list[float]
    chikou: list[float]


def ichimoku_cloud(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> IchimokuCloudResult:
    """
    Ichimoku Cloud:
    - tenkan-sen:  (max(high, tenkan_period)  + min(low, tenkan_period))  / 2
    - kijun-sen:   (max(high, kijun_period)   + min(low, kijun_period))   / 2
    - senkou A:    (tenkan + kijun) / 2, displaced forward by `displacement` bars
    - senkou B:    (max(high, senkou_b_period) + min(low, senkou_b_period)) / 2, displaced forward
    - chikou:      close shifted back by `displacement` bars
    """
    n = len(closes)
    max_h_t = _rolling_max(highs, tenkan_period)
    min_l_t = _rolling_min(lows, tenkan_period)
    max_h_k = _rolling_max(highs, kijun_period)
    min_l_k = _rolling_min(lows, kijun_period)
    max_h_b = _rolling_max(highs, senkou_b_period)
    min_l_b = _rolling_min(lows, senkou_b_period)

    tenkan = [float("nan")] * n
    kijun = [float("nan")] * n
    senkou_a_full = [float("nan")] * (n + displacement)
    senkou_b_full = [float("nan")] * (n + displacement)
    chikou = [float("nan")] * n

    for i in range(n):
        if not math.isnan(max_h_t[i]) and not math.isnan(min_l_t[i]):
            tenkan[i] = (max_h_t[i] + min_l_t[i]) / 2
        if not math.isnan(max_h_k[i]) and not math.isnan(min_l_k[i]):
            kijun[i] = (max_h_k[i] + min_l_k[i]) / 2
        if not math.isnan(tenkan[i]) and not math.isnan(kijun[i]):
            senkou_a_full[i + displacement] = (tenkan[i] + kijun[i]) / 2
        if not math.isnan(max_h_b[i]) and not math.isnan(min_l_b[i]):
            senkou_b_full[i + displacement] = (max_h_b[i] + min_l_b[i]) / 2
        if i - displacement >= 0:
            chikou[i - displacement] = closes[i]

    return IchimokuCloudResult(
        tenkan=tenkan,
        kijun=kijun,
        senkou_a=senkou_a_full[:n],
        senkou_b=senkou_b_full[:n],
        chikou=chikou,
    )


# ─── SuperTrend ───────────────────────────────────────────────────────────────


class SuperTrendResult(NamedTuple):
    values: list[float]
    direction: list[float]  # 1 = uptrend, -1 = downtrend


def super_trend(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 10,
    multiplier: float = 3.0,
) -> SuperTrendResult:
    """
    SuperTrend indicator.
    - upperBand = ((high+low)/2) + multiplier*ATR
    - lowerBand = ((high+low)/2) - multiplier*ATR
    - direction: 1 = uptrend, -1 = downtrend
    """
    n = len(closes)
    atr_values = _atr(highs, lows, closes, period)
    values = [float("nan")] * n
    direction = [float("nan")] * n

    upper_band = float("nan")
    lower_band = float("nan")
    prev_upper = float("nan")
    prev_lower = float("nan")
    prev_dir = 1

    for i in range(period, n):
        if math.isnan(atr_values[i]):
            continue
        hl2 = (highs[i] + lows[i]) / 2
        raw_upper = hl2 + multiplier * atr_values[i]
        raw_lower = hl2 - multiplier * atr_values[i]

        upper_band = (
            raw_upper
            if (math.isnan(prev_upper) or raw_upper < prev_upper or closes[i - 1] > prev_upper)
            else prev_upper
        )
        lower_band = (
            raw_lower
            if (math.isnan(prev_lower) or raw_lower > prev_lower or closes[i - 1] < prev_lower)
            else prev_lower
        )

        if closes[i] <= upper_band:
            d = -1
        else:
            d = 1
        if prev_dir == -1 and not math.isnan(prev_upper) and closes[i] > prev_upper:
            d = 1
        if prev_dir == 1 and not math.isnan(prev_lower) and closes[i] < prev_lower:
            d = -1

        values[i] = lower_band if d == 1 else upper_band
        direction[i] = d
        prev_upper = upper_band
        prev_lower = lower_band
        prev_dir = d

    return SuperTrendResult(values=values, direction=direction)


# ─── TRIX ─────────────────────────────────────────────────────────────────────


def trix(closes: list[float], period: int) -> list[float]:
    """
    TRIX — triple-smoothed EMA, then 1-period Rate of Change.
    Returns percentage change * 100.
    """
    n = len(closes)
    e1 = _ema(closes, period)
    valid_e1 = [v for v in e1 if not math.isnan(v)]
    e2 = _ema(valid_e1, period)
    valid_e2 = [v for v in e2 if not math.isnan(v)]
    e3 = _ema(valid_e2, period)

    result = [float("nan")] * n
    e3_start = n - len(e3)
    for i in range(1, len(e3)):
        if not math.isnan(e3[i]) and not math.isnan(e3[i - 1]) and e3[i - 1] != 0:
            result[e3_start + i] = ((e3[i] - e3[i - 1]) / e3[i - 1]) * 100
    return result


# ─── ROC ──────────────────────────────────────────────────────────────────────


def roc(closes: list[float], period: int) -> list[float]:
    """
    Rate of Change:
    ROC[i] = (close[i] - close[i-period]) / close[i-period] * 100
    """
    n = len(closes)
    result = [float("nan")] * n
    for i in range(period, n):
        if closes[i - period] != 0:
            result[i] = ((closes[i] - closes[i - period]) / closes[i - period]) * 100
    return result


# ─── Ultimate Oscillator ──────────────────────────────────────────────────────


def ultimate_oscillator(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period1: int = 7,
    period2: int = 14,
    period3: int = 28,
) -> list[float]:
    """
    Ultimate Oscillator:
    BP  = close - min(low, prev_close)
    TR  = max(high, prev_close) - min(low, prev_close)
    Weighted avg over 3 periods with 4:2:1 ratio, scaled 0–100.
    """
    n = len(closes)
    result = [float("nan")] * n
    bp = [float("nan")] * n
    tr = [float("nan")] * n

    for i in range(1, n):
        prev_close = closes[i - 1]
        true_high = max(highs[i], prev_close)
        true_low = min(lows[i], prev_close)
        bp[i] = closes[i] - true_low
        tr[i] = true_high - true_low

    min_period = max(period1, period2, period3)
    for i in range(min_period, n):
        sum_bp1 = sum(bp[i - period1 + 1 : i + 1])
        sum_tr1 = sum(tr[i - period1 + 1 : i + 1])
        sum_bp2 = sum(bp[i - period2 + 1 : i + 1])
        sum_tr2 = sum(tr[i - period2 + 1 : i + 1])
        sum_bp3 = sum(bp[i - period3 + 1 : i + 1])
        sum_tr3 = sum(tr[i - period3 + 1 : i + 1])
        if sum_tr1 == 0 or sum_tr2 == 0 or sum_tr3 == 0:
            continue
        avg1 = sum_bp1 / sum_tr1
        avg2 = sum_bp2 / sum_tr2
        avg3 = sum_bp3 / sum_tr3
        result[i] = (100 * (4 * avg1 + 2 * avg2 + avg3)) / 7
    return result
