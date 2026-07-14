"""
Unit tests — IV surface endpoint helpers.
"""

from __future__ import annotations

from app.api.v1.options import _build_demo_surface


class TestDemoSurface:
    def test_returns_non_empty_list(self) -> None:
        surface = _build_demo_surface()
        assert len(surface) > 0

    def test_all_required_keys_present(self) -> None:
        surface = _build_demo_surface()
        for pt in surface:
            assert "strike" in pt
            assert "expiry_days" in pt
            assert "iv" in pt
            assert "contract_type" in pt

    def test_iv_values_are_positive(self) -> None:
        surface = _build_demo_surface()
        for pt in surface:
            assert pt["iv"] > 0, f"IV <= 0 for {pt}"

    def test_iv_values_in_realistic_range(self) -> None:
        surface = _build_demo_surface()
        for pt in surface:
            assert 0.0 < pt["iv"] < 2.0, f"IV {pt['iv']} out of range"

    def test_expiry_days_are_positive(self) -> None:
        surface = _build_demo_surface()
        for pt in surface:
            assert pt["expiry_days"] > 0

    def test_skew_otm_puts_higher_iv_than_atm(self) -> None:
        """OTM puts (strike < ATM) should have higher IV than ATM."""
        surface = _build_demo_surface()
        by_exp: dict[int, dict[float, float]] = {}
        for pt in surface:
            exp = pt["expiry_days"]
            if exp not in by_exp:
                by_exp[exp] = {}
            by_exp[exp][pt["strike"]] = pt["iv"]

        # Check one expiry — ATM = 100.0, OTM put = 80.0
        exp30 = by_exp.get(30, {})
        if 80.0 in exp30 and 100.0 in exp30:
            assert exp30[80.0] > exp30[100.0], (
                f"OTM put IV {exp30[80.0]} should exceed ATM IV {exp30[100.0]}"
            )
