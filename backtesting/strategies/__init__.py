"""Built-in demo strategies."""
from backtesting.strategies.bollinger_band import BollingerBandStrategy
from backtesting.strategies.macd_cross import MACDCrossStrategy
from backtesting.strategies.rsi_mean_reversion import RSIMeanReversionStrategy
from backtesting.strategies.sma_cross import SmaCrossStrategy
from backtesting.strategies.vwap_reversion import VWAPReversionStrategy

__all__ = [
    "SmaCrossStrategy",
    "RSIMeanReversionStrategy",
    "MACDCrossStrategy",
    "BollingerBandStrategy",
    "VWAPReversionStrategy",
]
