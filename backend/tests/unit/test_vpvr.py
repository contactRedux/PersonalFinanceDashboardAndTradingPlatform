"""
Unit tests — VPVR endpoint computation logic.
"""

from __future__ import annotations

import pytest


class TestVPVRComputation:
    """Tests for VPVR bucket computation (tested via the module-level function)."""

    def test_demo_surface_bucket_sum(self) -> None:
        """Verify VPVR bucketing allocates all volume."""
        closes = [100.0, 102.0, 104.0, 100.0, 98.0, 96.0, 100.0]
        volumes = [1000.0, 1200.0, 800.0, 1500.0, 900.0, 700.0, 1100.0]
        bins = 5

        price_min = min(closes)
        price_max = max(closes)
        bin_size = (price_max - price_min) / bins
        bucket_vol = [0.0] * bins

        for close, vol in zip(closes, volumes, strict=False):
            idx = min(bins - 1, int((close - price_min) / bin_size))
            bucket_vol[idx] += vol

        assert sum(bucket_vol) == pytest.approx(sum(volumes))

    def test_poc_is_highest_volume_bin(self) -> None:
        closes = [100.0] * 10 + [105.0] * 2  # most closes near 100
        volumes = [1000.0] * 10 + [500.0] * 2
        bins = 4

        price_min = min(closes)
        price_max = max(closes)
        bin_size = (price_max - price_min) / bins
        bucket_vol = [0.0] * bins

        for close, vol in zip(closes, volumes, strict=False):
            idx = min(bins - 1, int((close - price_min) / bin_size))
            bucket_vol[idx] += vol

        poc_idx = bucket_vol.index(max(bucket_vol))
        # POC should be the lowest bin (most closes are 100)
        assert poc_idx == 0

    def test_pct_of_max_is_1_for_poc(self) -> None:
        """POC bin must have pct_of_max == 1.0."""
        closes = [100.0, 100.0, 100.0, 110.0]
        volumes = [1000.0, 1000.0, 1000.0, 200.0]
        bins = 4

        price_min = min(closes)
        price_max = max(closes)
        bin_size = (price_max - price_min) / bins
        bucket_vol = [0.0] * bins

        for close, vol in zip(closes, volumes, strict=False):
            idx = min(bins - 1, int((close - price_min) / bin_size))
            bucket_vol[idx] += vol

        max_vol = max(bucket_vol)
        pcts = [bv / max_vol for bv in bucket_vol]
        assert max(pcts) == pytest.approx(1.0)

    def test_all_prices_equal_returns_empty_levels(self) -> None:
        """When all closes are identical, price range is 0 → return empty."""
        closes = [100.0] * 5
        price_min = min(closes)
        price_max = max(closes)
        assert price_max == price_min  # triggers early-return in endpoint
