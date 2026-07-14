# backtesting/strategies — Built-In Trading Strategies

## What is this folder?

A **trading strategy** is a set of rules that tells you *when* to buy and *when* to sell. This folder contains five pre-built strategies that are ready to use immediately in the backtesting engine.

Each strategy is a simple Python class with one key method: `generate_signals(data)`. It takes historical price data and outputs a signal for every day: **+1** (buy / hold long), **-1** (sell / go short), or **0** (do nothing, stay flat).

---

## The Five Strategies

### `sma_cross.py` — **`SmaCrossStrategy`** (Simplest)
**Analogy:** Two moving averages — a "fast" one (tracks recent prices closely) and a "slow" one (a more distant average). When the fast average crosses above the slow one, the short-term trend is turning up — buy. When it crosses below — sell.

**SMA** = Simple Moving Average — the plain arithmetic average of the last N closing prices.

- **`fast`** (default 20): the number of days for the short-term average
- **`slow`** (default 50): the number of days for the long-term average
- **`allow_short`** (default False): if True, also goes short when fast < slow

**`generate_signals(data)`** — Returns +1 wherever fast SMA > slow SMA (uptrend), -1 wherever fast < slow and allow_short is True, 0 otherwise.

---

### `macd_cross.py` — **`MACDCrossStrategy`**
**MACD** (Moving Average Convergence Divergence — a momentum indicator showing when the short-term trend is diverging from the long-term trend).

The MACD line is computed as EMA(12) − EMA(26). A 9-period EMA of the MACD line is called the "signal line." A bullish crossover (MACD crosses above signal) generates a buy; a bearish crossover generates a sell.

- **`fast`** (default 12), **`slow`** (default 26), **`signal`** (default 9)
- **`allow_short`**: if True, go short on bearish crosses

**`generate_signals(data)`** — Detects MACD/signal crossovers using `pandas.ewm()` (exponential weighted moving average, the same formula used by TA-Lib). Carries the signal forward until an opposite cross, so you hold until the trend reverses.

---

### `rsi_mean_reversion.py` — **`RSIMeanReversionStrategy`**
**RSI** (Relative Strength Index — a 0-100 scale measuring whether a stock is overbought or oversold). Traditionally: below 30 = oversold (may bounce up), above 70 = overbought (may fall).

This is a **mean reversion** strategy (the idea that prices tend to return to their average after an extreme move — like a rubber band snapping back).

- **`period`** (default 14): RSI lookback window
- **`oversold`** (default 30): RSI level below which to buy
- **`overbought`** (default 70): RSI level above which to exit / go short

**`generate_signals(data)`** — Uses Wilder's smoothing (identical to TA-Lib's RSI formula) via `pandas.ewm()`. Returns +1 where RSI < oversold, -1 where RSI > overbought (if allow_short=True), 0 otherwise.

---

### `bollinger_band.py` — **`BollingerBandStrategy`**
**Bollinger Bands** — three lines around a moving average: the middle line is a 20-day SMA; the upper and lower bands are 2 standard deviations above and below it. When price touches the lower band, it's statistically "stretched" downward and may bounce. When it touches the upper band, it may fall.

Another mean reversion strategy.

- **`period`** (default 20), **`std_dev`** (default 2.0)

**`generate_signals(data)`** — Buys when price closes below the lower band; exits (or shorts) when price closes above the upper band.

---

### `vwap_reversion.py` — **`VWAPReversionStrategy`**
**VWAP** (Volume-Weighted Average Price — the average price of a stock over the trading day, weighted by volume). Think of it as the "fair price" that institutional traders use as a benchmark.

Intraday traders use VWAP reversion: if price drops significantly below VWAP, it may snap back up.

- **`threshold_pct`**: how far below VWAP (as a %) to trigger a buy signal

**`generate_signals(data)`** — Generates buy signals when the current price is more than `threshold_pct` below the rolling VWAP, sells when price returns to VWAP.

---

## Adding a New Strategy

A custom strategy just needs to implement `generate_signals(data: pd.DataFrame) -> pd.Series`. It works automatically with both the `VectorizedEngine` and `EventDrivenEngine`, and with all three optimizers.

```python
class MyStrategy:
    def __init__(self, my_param: int = 14) -> None:
        self.my_param = my_param

    def generate_signals(self, data):
        # data has columns: open, high, low, close, volume
        # return a Series of +1, 0, -1 aligned to data.index
        ...
```

---

## How does this connect to the rest of the app?

- The `backend/app/api/v1/backtest.py` endpoint imports these classes by name (mapped in the `_get_strategy()` helper function)
- The `StrategyBuilderPanel` in the frontend lets users configure strategy parameters visually
- Optimization tools in `backtesting/optimization/` instantiate these classes repeatedly with different parameters to find the best settings
