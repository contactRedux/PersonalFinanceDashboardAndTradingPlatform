"""
Unit tests — Risk metrics (ratios.py) and Options Greeks (greeks.py).

Covers:
  - historical_var / cvar
  - sharpe_ratio / sortino_ratio / calmar_ratio
  - beta_alpha
  - max_drawdown
  - position_size_kelly
  - black_scholes_greeks (call/put)
  - implied_volatility Newton-Raphson
"""
from __future__ import annotations

import math

import pytest
from app.services.options.greeks import black_scholes_greeks, implied_volatility
from app.services.risk.ratios import (
    beta_alpha,
    calmar_ratio,
    cvar,
    historical_var,
    max_drawdown,
    position_size_kelly,
    sharpe_ratio,
    sortino_ratio,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture()
def steady_returns() -> list[float]:
    """Alternating +0.15% / +0.05% — positive mean with non-zero variance."""
    return [0.0015, 0.0005] * 126  # 252 returns, mean=0.001, stdev>0


@pytest.fixture()
def volatile_returns() -> list[float]:
    """Alternating +5% / -4% — net positive but high volatility."""
    return [0.05, -0.04] * 126


@pytest.fixture()
def loss_heavy_returns() -> list[float]:
    """Heavy left tail: 90% of days -1%, 10% -5%."""
    return [-0.01] * 227 + [-0.05] * 25


@pytest.fixture()
def mixed_negative_returns() -> list[float]:
    """Mostly negative with some variance: alternating -0.5% / -1.5%."""
    return [-0.005, -0.015] * 126


# ─── historical_var ────────────────────────────────────────────────────────────
class TestHistoricalVar:
    def test_positive_value(self, volatile_returns: list[float]) -> None:
        result = historical_var(volatile_returns, 0.95)
        assert result > 0

    def test_var_less_than_worst_loss(self, loss_heavy_returns: list[float]) -> None:
        var = historical_var(loss_heavy_returns, 0.95)
        worst = max(abs(r) for r in loss_heavy_returns)
        assert var <= worst

    def test_99_greater_than_95(self, loss_heavy_returns: list[float]) -> None:
        var_95 = historical_var(loss_heavy_returns, 0.95)
        var_99 = historical_var(loss_heavy_returns, 0.99)
        assert var_99 >= var_95

    def test_empty_returns_zero(self) -> None:
        assert historical_var([], 0.95) == 0.0


# ─── cvar ──────────────────────────────────────────────────────────────────────
class TestCVar:
    def test_cvar_exceeds_var(self, loss_heavy_returns: list[float]) -> None:
        var = historical_var(loss_heavy_returns, 0.95)
        es = cvar(loss_heavy_returns, 0.95)
        assert es >= var

    def test_empty_returns_zero(self) -> None:
        assert cvar([], 0.95) == 0.0

    def test_positive_value(self, loss_heavy_returns: list[float]) -> None:
        assert cvar(loss_heavy_returns, 0.95) > 0


# ─── sharpe_ratio ──────────────────────────────────────────────────────────────
class TestSharpeRatio:
    def test_steady_positive_returns_positive_sharpe(
        self, steady_returns: list[float]
    ) -> None:
        # steady_returns: mean=0.001/day, stdev > 0, annualized return > risk-free
        sharpe = sharpe_ratio(steady_returns, risk_free_rate=0.03)
        assert sharpe > 0

    def test_zero_with_single_return(self) -> None:
        assert sharpe_ratio([0.001]) == 0.0

    def test_negative_returns_negative_sharpe(
        self, mixed_negative_returns: list[float]
    ) -> None:
        # mixed_negative: mean = -0.01/day → annualized far below risk-free
        assert sharpe_ratio(mixed_negative_returns) < 0


# ─── sortino_ratio ─────────────────────────────────────────────────────────────
class TestSortinoRatio:
    def test_positive_returns_no_downside(self) -> None:
        positive_only = [0.01] * 252
        result = sortino_ratio(positive_only)
        assert result == float("inf") or result > 0

    def test_mixed_returns(self, volatile_returns: list[float]) -> None:
        result = sortino_ratio(volatile_returns)
        assert isinstance(result, float)
        assert math.isfinite(result)

    def test_all_negative_returns_negative_sortino(
        self, mixed_negative_returns: list[float]
    ) -> None:
        # mixed_negative has downside deviation > 0 and negative mean
        result = sortino_ratio(mixed_negative_returns)
        assert result < 0


# ─── max_drawdown ──────────────────────────────────────────────────────────────
class TestMaxDrawdown:
    def test_monotonic_growth_zero_drawdown(self) -> None:
        curve = [100 + i for i in range(100)]
        dd, duration = max_drawdown(curve)
        assert dd == 0.0
        assert duration == 0

    def test_single_drop_correct_drawdown(self) -> None:
        curve = [100.0, 80.0, 90.0]
        dd, _ = max_drawdown(curve)
        # Max drawdown: (100-80)/100 = 0.2
        assert abs(dd - 0.2) < 1e-5

    def test_duration_positive_after_recovery(self) -> None:
        curve = [100.0, 50.0, 90.0, 100.0, 110.0]
        _, duration = max_drawdown(curve)
        assert duration > 0

    def test_too_short_returns_zeros(self) -> None:
        dd, dur = max_drawdown([100.0])
        assert dd == 0.0
        assert dur == 0


# ─── calmar_ratio ──────────────────────────────────────────────────────────────
class TestCalmarRatio:
    def test_positive_with_positive_returns(self, volatile_returns: list[float]) -> None:
        # volatile_returns: [+5%, -4%] alternating — net positive with real drawdowns
        equity = [100_000.0]
        for r in volatile_returns:
            equity.append(equity[-1] * (1 + r))
        result = calmar_ratio(volatile_returns, equity)
        assert result > 0

    def test_empty_returns_zero(self) -> None:
        assert calmar_ratio([], []) == 0.0


# ─── beta_alpha ────────────────────────────────────────────────────────────────
class TestBetaAlpha:
    def test_identical_returns_beta_one(self) -> None:
        rets = [0.001, -0.002, 0.003, 0.0, -0.001] * 50
        beta, _ = beta_alpha(rets, rets)
        assert abs(beta - 1.0) < 0.01

    def test_zero_variance_benchmark_returns_default(self) -> None:
        rets = [0.001] * 10
        flat_benchmark = [0.001] * 10  # zero variance
        beta, alpha = beta_alpha(rets, flat_benchmark)
        assert isinstance(beta, float)
        assert isinstance(alpha, float)

    def test_too_short_returns_defaults(self) -> None:
        beta, alpha = beta_alpha([0.01], [0.01])
        assert beta == 1.0
        assert alpha == 0.0


# ─── position_size_kelly ───────────────────────────────────────────────────────
class TestPositionSizeKelly:
    def test_favorable_setup_returns_positive(self) -> None:
        result = position_size_kelly(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
        assert result > 0

    def test_negative_edge_returns_zero(self) -> None:
        result = position_size_kelly(win_rate=0.3, avg_win=1.0, avg_loss=2.0)
        assert result == 0.0

    def test_capped_at_25_pct(self) -> None:
        result = position_size_kelly(win_rate=0.95, avg_win=10.0, avg_loss=1.0)
        assert result <= 0.25

    def test_zero_avg_loss_returns_zero(self) -> None:
        assert position_size_kelly(0.6, 2.0, 0.0) == 0.0


# ─── black_scholes_greeks ──────────────────────────────────────────────────────
class TestBlackScholesGreeks:
    def test_call_delta_between_0_and_1(self) -> None:
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert 0 < g.delta < 1

    def test_put_delta_between_minus1_and_0(self) -> None:
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="put")
        assert -1 < g.delta < 0

    def test_atm_call_delta_near_half(self) -> None:
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.0, sigma=0.2, option_type="call")
        # ATM call delta ≈ 0.5 (exact value depends on vol and time)
        assert abs(g.delta - 0.5) < 0.1

    def test_gamma_positive(self) -> None:
        g = black_scholes_greeks(S=100, K=100, T=0.5, r=0.05, sigma=0.3, option_type="call")
        assert g.gamma > 0

    def test_vega_positive(self) -> None:
        g = black_scholes_greeks(S=100, K=100, T=0.5, r=0.05, sigma=0.3, option_type="call")
        assert g.vega > 0

    def test_theta_negative(self) -> None:
        # Theta should be negative (time decay)
        g = black_scholes_greeks(S=100, K=100, T=0.5, r=0.05, sigma=0.3, option_type="call")
        assert g.theta < 0

    def test_deep_itm_call_delta_near_1(self) -> None:
        g = black_scholes_greeks(S=200, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert g.delta > 0.95

    def test_deep_otm_call_delta_near_0(self) -> None:
        g = black_scholes_greeks(S=50, K=200, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert g.delta < 0.05

    def test_call_put_parity_greeks(self) -> None:
        """Delta parity: call_delta - put_delta ≈ 1."""
        call = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        put = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="put")
        assert abs((call.delta + abs(put.delta)) - 1.0) < 0.02

    def test_zero_time_handled_gracefully(self) -> None:
        # T=0 should not raise; defaults to T=0.0001
        g = black_scholes_greeks(S=100, K=100, T=0.0, r=0.05, sigma=0.2, option_type="call")
        assert isinstance(g.delta, float)


# ─── implied_volatility ────────────────────────────────────────────────────────
class TestImpliedVolatility:
    def test_round_trip_iv(self) -> None:
        """Price with sigma=0.3, then recover sigma from that price."""
        g = black_scholes_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.3, option_type="call")
        recovered_iv = implied_volatility(
            market_price=g.theoretical_price,
            S=100, K=100, T=0.25, r=0.05, option_type="call",
        )
        assert recovered_iv is not None
        assert abs(recovered_iv - 0.3) < 0.001

    def test_zero_price_returns_none(self) -> None:
        assert implied_volatility(0.0, S=100, K=100, T=0.25, r=0.05) is None

    def test_negative_time_returns_none(self) -> None:
        assert implied_volatility(5.0, S=100, K=100, T=-0.1, r=0.05) is None

    def test_put_round_trip_iv(self) -> None:
        g = black_scholes_greeks(S=100, K=105, T=0.5, r=0.04, sigma=0.25, option_type="put")
        recovered = implied_volatility(
            g.theoretical_price, S=100, K=105, T=0.5, r=0.04, option_type="put"
        )
        assert recovered is not None
        assert abs(recovered - 0.25) < 0.005
