"""
Momentum and trend indicator implementations — pure Python, no dependencies.

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


def _rsi(closes: list[float], period: int) -> list[float]:
    n = len(closes)
    result = [float("nan")] * n
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0:
            avg_gain += change
        else:
            avg_loss += abs(change)
    avg_gain /= period
    avg_loss /= period
    result[period] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        change = closes[i] - closes[i - 1]
        gain = change if change > 0 else 0.0
        loss = abs(change) if change < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        result[i] = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return result


# ─── Exported indicators ─────────────────────────────────────────────────────


class StochasticRsiResult(NamedTuple):
    k: list[float]
    d: list[float]


def stochastic_rsi(
    closes: list[float],
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> StochasticRsiResult:
    """RSI of RSI, smoothed with two SMAs."""
    rsi_values = _rsi(closes, period)
    n = len(closes)
    raw_k: list[float] = [float("nan")] * n

    for i in range(period * 2 - 2, n):
        window = [v for v in rsi_values[i - period + 1 : i + 1] if not math.isnan(v)]
        if not window:
            continue
        min_rsi = min(window)
        max_rsi = max(window)
        rng = max_rsi - min_rsi
        if not math.isnan(rsi_values[i]):
            raw_k[i] = 0.0 if rng == 0 else ((rsi_values[i] - min_rsi) / rng) * 100

    valid_raw = [v for v in raw_k if not math.isnan(v)]
    k_smooth = _sma(valid_raw, smooth_k)
    d_smooth = _sma([v for v in k_smooth if not math.isnan(v)], smooth_d)

    k: list[float] = [float("nan")] * n
    d: list[float] = [float("nan")] * n
    k_idx = 0
    for i in range(n):
        if not math.isnan(raw_k[i]) and k_idx < len(k_smooth) and not math.isnan(k_smooth[k_idx]):
            k[i] = k_smooth[k_idx]
            k_idx += 1

    d_idx = 0
    for i in range(n):
        if not math.isnan(k[i]) and d_idx < len(d_smooth) and not math.isnan(d_smooth[d_idx]):
            d[i] = d_smooth[d_idx]
            d_idx += 1

    return StochasticRsiResult(k=k, d=d)


def cci(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 20,
) -> list[float]:
    """CCI — (Typical Price − SMA of TP) / (0.015 × Mean Deviation)."""
    n = len(closes)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        tps = [(highs[j] + lows[j] + closes[j]) / 3 for j in range(i - period + 1, i + 1)]
        mean_tp = sum(tps) / period
        mean_dev = sum(abs(tp - mean_tp) for tp in tps) / period
        result[i] = 0.0 if mean_dev == 0 else (tps[-1] - mean_tp) / (0.015 * mean_dev)
    return result


def williams_r(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float]:
    """Williams %R — (Highest High − Close) / (Highest High − Lowest Low) × −100."""
    n = len(closes)
    result = [float("nan")] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        rng = hh - ll
        result[i] = -50.0 if rng == 0 else ((hh - closes[i]) / rng) * -100
    return result


def parabolic_sar(
    highs: list[float],
    lows: list[float],
    step: float = 0.02,
    maximum: float = 0.2,
) -> list[float]:
    """Standard Wilder Parabolic SAR."""
    n = len(highs)
    if n < 2:
        return [float("nan")] * n
    result = [float("nan")] * n
    is_long = True
    sar = lows[0]
    ep = highs[0]
    af = step
    result[0] = sar

    for i in range(1, n):
        prev_sar = sar
        if is_long:
            sar = prev_sar + af * (ep - prev_sar)
            sar = min(sar, lows[i - 1], lows[i - 2] if i >= 2 else lows[i - 1])
            if highs[i] > ep:
                ep = highs[i]
                af = min(af + step, maximum)
            if lows[i] < sar:
                is_long = False
                sar = ep
                ep = lows[i]
                af = step
        else:
            sar = prev_sar + af * (ep - prev_sar)
            sar = max(sar, highs[i - 1], highs[i - 2] if i >= 2 else highs[i - 1])
            if lows[i] < ep:
                ep = lows[i]
                af = min(af + step, maximum)
            if highs[i] > sar:
                is_long = True
                sar = ep
                ep = highs[i]
                af = step
        result[i] = sar
    return result


class DonchianChannelResult(NamedTuple):
    upper: list[float]
    lower: list[float]
    mid: list[float]


def donchian_channel(
    highs: list[float],
    lows: list[float],
    period: int = 20,
) -> DonchianChannelResult:
    """Rolling max high / min low; mid = (upper + lower) / 2."""
    n = len(highs)
    upper = [float("nan")] * n
    lower = [float("nan")] * n
    mid = [float("nan")] * n
    for i in range(period - 1, n):
        max_h = max(highs[i - period + 1 : i + 1])
        min_l = min(lows[i - period + 1 : i + 1])
        upper[i] = max_h
        lower[i] = min_l
        mid[i] = (max_h + min_l) / 2
    return DonchianChannelResult(upper=upper, lower=lower, mid=mid)


class KeltnerChannelResult(NamedTuple):
    upper: list[float]
    mid: list[float]
    lower: list[float]


def keltner_channel(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    atr_period: int = 20,
    multiplier: float = 2.0,
) -> KeltnerChannelResult:
    """EMA ± multiplier × ATR."""
    n = len(closes)
    mid_line = _ema(closes, atr_period)
    atr_values = _atr(highs, lows, closes, atr_period)
    upper = [float("nan")] * n
    mid = [float("nan")] * n
    lower = [float("nan")] * n
    for i in range(n):
        if not math.isnan(mid_line[i]) and not math.isnan(atr_values[i]):
            mid[i] = mid_line[i]
            upper[i] = mid_line[i] + multiplier * atr_values[i]
            lower[i] = mid_line[i] - multiplier * atr_values[i]
    return KeltnerChannelResult(upper=upper, mid=mid, lower=lower)
