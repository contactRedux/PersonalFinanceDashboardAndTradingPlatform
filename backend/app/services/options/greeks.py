"""
Black-Scholes Greeks implementation.

Computes all five Greeks (Delta, Gamma, Theta, Vega, Rho) plus
Implied Volatility (IV) for options pricing analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    theoretical_price: float
    iv: float | None = None


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_greeks(  # noqa: N802
    S: float,        # noqa: N803  # Current stock price
    K: float,        # noqa: N803  # Strike price
    T: float,        # noqa: N803  # Time to expiration in years
    r: float,        # Risk-free interest rate (annualized)
    sigma: float,    # Implied volatility (annualized)
    option_type: str = "call",  # "call" or "put"
) -> Greeks:
    """
    Compute Black-Scholes option price and all Greeks.
    T must be > 0 (use a minimum of 0.0001 for expiry-day options).
    S, K, T follow standard Black-Scholes notation (uppercase per convention).
    """
    if T <= 0:
        T = 0.0001  # noqa: N806
    if sigma <= 0:
        sigma = 0.0001

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type.lower() == "call":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        rho = K * T * math.exp(-r * T) * _norm_cdf(d2) / 100
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
        rho = -K * T * math.exp(-r * T) * _norm_cdf(-d2) / 100

    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * _norm_pdf(d1) * math.sqrt(T) / 100
    theta = (
        -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * K * math.exp(-r * T) * (_norm_cdf(d2) if option_type == "call" else _norm_cdf(-d2))
    ) / 365

    return Greeks(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        theta=round(theta, 6),
        vega=round(vega, 6),
        rho=round(rho, 6),
        theoretical_price=round(price, 4),
    )


def implied_volatility(  # noqa: N802
    market_price: float,
    S: float,        # noqa: N803
    K: float,        # noqa: N803
    T: float,        # noqa: N803
    r: float,
    option_type: str = "call",
    tolerance: float = 1e-5,
    max_iterations: int = 100,
) -> float | None:
    """
    Compute implied volatility via Newton-Raphson method.
    Returns None if IV cannot be solved within tolerance.
    """
    if T <= 0 or market_price <= 0:
        return None

    sigma = 0.3  # Initial guess: 30% IV
    for _ in range(max_iterations):
        greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
        price_diff = greeks.theoretical_price - market_price
        if abs(price_diff) < tolerance:
            return round(sigma, 6)
        vega = greeks.vega * 100  # vega is scaled by /100 above, undo it
        if abs(vega) < 1e-10:
            return None
        sigma -= price_diff / vega

    return round(sigma, 6) if 0 < sigma < 10 else None
