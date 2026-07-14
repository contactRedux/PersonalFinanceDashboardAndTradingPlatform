"""
Volume and structure indicator implementations — pure Python, no dependencies.

These mirror the TypeScript implementations in frontend/lib/indicators/index.ts
and are used by the backtesting engine and strategy evaluation service.
"""

from __future__ import annotations

import math
from typing import NamedTuple


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _sma(values: list[float], period: int) -> list[float]:
    n = len(values)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        result[i] = sum(values[i - period + 1 : i + 1]) / period
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


def _clv(high: float, low: float, close: float) -> float:
    """Close Location Value."""
    hl = high - low
    if hl == 0:
        return 0.0
    return ((close - low) - (high - close)) / hl


# ─── Exported indicators ─────────────────────────────────────────────────────


def accumulation_distribution(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
) -> list[float]:
    """
    Accumulation/Distribution Line.
    CLV = ((close - low) - (high - close)) / (high - low)
    AD[i] = AD[i-1] + CLV[i] * volume[i]
    """
    n = len(closes)
    result: list[float] = []
    ad = 0.0
    for i in range(n):
        ad += _clv(highs[i], lows[i], closes[i]) * volumes[i]
        result.append(ad)
    return result


def cmf(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    period: int = 20,
) -> list[float]:
    """Chaikin Money Flow — sum(CLV*vol, period) / sum(vol, period)."""
    n = len(closes)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        sum_clv_vol = 0.0
        sum_vol = 0.0
        for j in range(i - period + 1, i + 1):
            sum_clv_vol += _clv(highs[j], lows[j], closes[j]) * volumes[j]
            sum_vol += volumes[j]
        result[i] = 0.0 if sum_vol == 0 else sum_clv_vol / sum_vol
    return result


def mfi(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    period: int = 14,
) -> list[float]:
    """Money Flow Index — 100 - (100 / (1 + positive_mf / negative_mf))."""
    n = len(closes)
    result = [float("nan")] * n
    typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    raw_mf = [typical_prices[i] * volumes[i] for i in range(n)]

    for i in range(period, n):
        pos_mf = 0.0
        neg_mf = 0.0
        for j in range(i - period + 1, i + 1):
            if typical_prices[j] > typical_prices[j - 1]:
                pos_mf += raw_mf[j]
            elif typical_prices[j] < typical_prices[j - 1]:
                neg_mf += raw_mf[j]
        if neg_mf == 0:
            result[i] = 100.0
        else:
            result[i] = 100.0 - 100.0 / (1.0 + pos_mf / neg_mf)
    return result


def force_index(
    closes: list[float],
    volumes: list[float],
    period: int = 13,
) -> list[float]:
    """Force Index — EMA of (close[i] - close[i-1]) * volume[i]."""
    n = len(closes)
    raw_fi = [float("nan")] * n
    for i in range(1, n):
        raw_fi[i] = (closes[i] - closes[i - 1]) * volumes[i]

    valid_fi = raw_fi[1:]
    ema_fi = _ema(valid_fi, period)
    result = [float("nan")] * n
    for i in range(len(ema_fi)):
        result[i + 1] = ema_fi[i]
    return result


def rvol(
    volumes: list[float],
    period: int = 20,
) -> list[float]:
    """Relative Volume — volume[i] / SMA(volume, period)[i]."""
    sma_vol = _sma(volumes, period)
    n = len(volumes)
    result = [float("nan")] * n
    for i in range(n):
        if not math.isnan(sma_vol[i]) and sma_vol[i] != 0:
            result[i] = volumes[i] / sma_vol[i]
    return result


class PivotPointsResult(NamedTuple):
    P: list[float]
    R1: list[float]
    R2: list[float]
    R3: list[float]
    S1: list[float]
    S2: list[float]
    S3: list[float]


def pivot_points(
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> PivotPointsResult:
    """
    Standard floor pivot points (rolling, based on previous bar's H, L, C).
    First bar has NaN for all levels.
    """
    n = len(closes)
    P_arr = [float("nan")] * n
    R1_arr = [float("nan")] * n
    R2_arr = [float("nan")] * n
    R3_arr = [float("nan")] * n
    S1_arr = [float("nan")] * n
    S2_arr = [float("nan")] * n
    S3_arr = [float("nan")] * n

    for i in range(1, n):
        H = highs[i - 1]
        L = lows[i - 1]
        C = closes[i - 1]
        p = (H + L + C) / 3
        P_arr[i] = p
        R1_arr[i] = 2 * p - L
        S1_arr[i] = 2 * p - H
        R2_arr[i] = p + (H - L)
        S2_arr[i] = p - (H - L)
        R3_arr[i] = H + 2 * (p - L)
        S3_arr[i] = L - 2 * (H - p)

    return PivotPointsResult(
        P=P_arr, R1=R1_arr, R2=R2_arr, R3=R3_arr,
        S1=S1_arr, S2=S2_arr, S3=S3_arr,
    )
