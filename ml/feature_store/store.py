"""
Feature store — lightweight feature computation and caching.

Architecture:
  1. FeatureComputer: computes ML features from raw OHLCV bars.
     All computation is deterministic, vectorised (NumPy/Pandas), and runs
     in-process — no RPC required.
  2. FeatureStore: wraps FeatureComputer with a two-level cache:
       L1 — in-process Python dict (current process, ephemeral)
       L2 — Redis (shared across workers, configurable TTL)

Keys:
  `feature_store:{symbol}:{timeframe}:{end_date}`  → JSON-serialised feature dict

Usage::

    from ml.feature_store.store import FeatureStore, compute_features
    import pandas as pd

    # Compute directly (no caching)
    features = compute_features(df)          # df has OHLCV columns

    # With caching
    store = FeatureStore(redis_url="redis://localhost:6379/3")
    features = await store.get_or_compute("SPY", "1d", df, end_date="2024-01-31")
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_FEATURE_CACHE_TTL_SECONDS = 3600  # 1 hour default


# ─── Feature computation ──────────────────────────────────────────────────────


def compute_features(df: pd.DataFrame) -> dict[str, float]:
    """
    Compute ML features from a raw OHLCV DataFrame.

    The input DataFrame must have columns: open, high, low, close, volume
    (case-insensitive).  Expects at least 30 rows; returns empty dict for
    insufficient data.

    Features returned (all scalar floats):
      Momentum:   return_1d, return_5d, return_20d, rsi_14
      Volatility: atr_14, rolling_vol_20, bb_width_20
      Volume:     vwap_dev, obv_change_5d, vol_ratio_20
      Trend:      sma_50_200_ratio, ema_12_26_ratio
    """
    cols = {c.lower() for c in df.columns}
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(cols):
        logger.warning("feature_store.missing_columns", cols=list(cols))
        return {}

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_index()

    if len(df) < 30:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # ── Momentum ──────────────────────────────────────────────────────────────
    def safe_return(n: int) -> float:
        if len(close) <= n:
            return 0.0
        return float((close.iloc[-1] / close.iloc[-1 - n]) - 1)

    def rsi(n: int = 14) -> float:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(n).mean()
        loss = (-delta.clip(upper=0)).rolling(n).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        return float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    # ── Volatility ────────────────────────────────────────────────────────────
    def atr(n: int = 14) -> float:
        tr = pd.concat(
            [
                (high - low),
                (high - close.shift(1)).abs(),
                (close.shift(1) - low).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return float(tr.rolling(n).mean().iloc[-1])

    def bb_width(n: int = 20) -> float:
        sma = close.rolling(n).mean()
        std = close.rolling(n).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        mid = (upper + lower) / 2
        if float(mid.iloc[-1]) == 0:
            return 0.0
        return float((upper.iloc[-1] - lower.iloc[-1]) / mid.iloc[-1])

    # ── Volume ─────────────────────────────────────────────────────────────────
    def vwap_deviation() -> float:
        """Deviation of last close from VWAP (last 20 bars)."""
        recent = df.tail(20)
        typical = (recent["high"] + recent["low"] + recent["close"]) / 3
        vwap = (typical * recent["volume"]).sum() / (recent["volume"].sum() + 1e-9)
        if float(vwap) == 0:
            return 0.0
        return float((close.iloc[-1] - vwap) / vwap)

    def obv_change(n: int = 5) -> float:
        obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
        if len(obv) < n + 1:
            return 0.0
        return float(obv.iloc[-1] - obv.iloc[-1 - n])

    def volume_ratio(n: int = 20) -> float:
        avg_vol = volume.rolling(n).mean().iloc[-1]
        if avg_vol == 0:
            return 1.0
        return float(volume.iloc[-1] / avg_vol)

    # ── Trend ──────────────────────────────────────────────────────────────────
    def sma_ratio(short: int = 50, long: int = 200) -> float:
        if len(close) < long:
            return 1.0
        s = close.rolling(short).mean().iloc[-1]
        l_ = close.rolling(long).mean().iloc[-1]
        return float(s / l_) if l_ != 0 else 1.0

    def ema_ratio(short: int = 12, long: int = 26) -> float:
        s = close.ewm(span=short, adjust=False).mean().iloc[-1]
        l_ = close.ewm(span=long, adjust=False).mean().iloc[-1]
        return float(s / l_) if l_ != 0 else 1.0

    return {
        "return_1d": safe_return(1),
        "return_5d": safe_return(5),
        "return_20d": safe_return(20),
        "rsi_14": rsi(14),
        "atr_14": atr(14),
        "rolling_vol_20": float(close.pct_change().rolling(20).std().iloc[-1]),
        "bb_width_20": bb_width(20),
        "vwap_dev": vwap_deviation(),
        "obv_change_5d": obv_change(5),
        "vol_ratio_20": volume_ratio(20),
        "sma_50_200_ratio": sma_ratio(50, 200),
        "ema_12_26_ratio": ema_ratio(12, 26),
    }


# ─── Caching layer ────────────────────────────────────────────────────────────


def _cache_key(symbol: str, timeframe: str, end_date: str) -> str:
    raw = f"feature_store:{symbol.upper()}:{timeframe}:{end_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class FeatureStore:
    """
    Two-level cached feature store (L1 in-process dict, L2 Redis).

    Parameters
    ----------
    redis_url:
        Redis connection URL.  When None (default), L2 caching is disabled
        and only L1 (in-process) caching is used.
    ttl_seconds:
        How long feature vectors stay valid in the Redis cache.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int = _FEATURE_CACHE_TTL_SECONDS,
    ) -> None:
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._l1: dict[str, dict[str, float]] = {}
        self._redis: Any | None = None

    async def _get_redis(self):  # type: ignore[return]
        """Return a shared redis.asyncio.Redis client (lazy init)."""
        if self._redis is None and self._redis_url:
            try:
                import redis.asyncio as aioredis  # noqa: PLC0415

                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                logger.warning("feature_store.redis_unavailable")
        return self._redis

    async def _l2_get(self, key: str) -> dict[str, float] | None:
        r = await self._get_redis()
        if r is None:
            return None
        try:
            val = await r.get(key)
            if val:
                return json.loads(val)
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _l2_set(self, key: str, features: dict[str, float]) -> None:
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.setex(key, self._ttl, json.dumps(features))
        except Exception:  # noqa: BLE001
            pass

    async def get_or_compute(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        end_date: str | None = None,
    ) -> dict[str, float]:
        """
        Return cached features if available, else compute and cache them.

        Parameters
        ----------
        symbol:
            Ticker symbol (used as part of the cache key).
        timeframe:
            Candle interval, e.g. '1d', '1h' (part of cache key).
        df:
            Raw OHLCV DataFrame — used if no cached value is found.
        end_date:
            Optional ISO date string for the cache key.  If None, today's
            date is used so that the cache naturally expires each day.
        """
        if end_date is None:
            end_date = datetime.now(UTC).date().isoformat()

        key = _cache_key(symbol, timeframe, end_date)

        # L1 — in-process
        if key in self._l1:
            return self._l1[key]

        # L2 — Redis
        cached = await self._l2_get(key)
        if cached is not None:
            self._l1[key] = cached
            return cached

        # Compute
        features = compute_features(df)
        if features:
            self._l1[key] = features
            await self._l2_set(key, features)
            logger.debug("feature_store.computed", symbol=symbol, n_features=len(features))

        return features

    def invalidate(self, symbol: str, timeframe: str, end_date: str) -> None:
        """Remove a specific entry from the L1 cache."""
        key = _cache_key(symbol, timeframe, end_date)
        self._l1.pop(key, None)
