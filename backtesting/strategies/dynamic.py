"""
DynamicStrategy — interprets a JSON node graph into strategy signals.

The node graph format is the same JSON produced by the StrategyBuilderPanel
frontend canvas.  A graph consists of nodes and edges:

  nodes: list of {id, type, data}
  edges: list of {source, target}

Node types:
  "indicator"  — computes a technical indicator value (e.g. RSI, SMA)
  "comparator" — compares two values (>, <, crosses_above, crosses_below)
  "logic"      — combines two boolean signals (AND, OR)
  "entry"      — entry action (buy / sell)
  "exit"       — exit action

Simple "RSI < 30 → buy" example graph::

    nodes:
      {id: "n1", type: "indicator", data: {indicator: "rsi", period: 14}}
      {id: "n2", type: "comparator", data: {op: "lt", value: 30}}
      {id: "n3", type: "entry", data: {side: "buy"}}
    edges:
      {source: "n1", target: "n2"}
      {source: "n2", target: "n3"}
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _compute_indicator(df: pd.DataFrame, node_data: dict) -> pd.Series:
    """Compute a single indicator series from node data."""
    indicator = node_data.get("indicator", "sma").lower()
    period = int(node_data.get("period", 14))
    close = df["close"]

    if indicator == "sma":
        return close.rolling(period).mean()
    if indicator == "ema":
        return close.ewm(span=period, adjust=False).mean()
    if indicator in ("rsi", "rsi14"):
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
    if indicator == "macd":
        fast = int(node_data.get("fast", 12))
        slow = int(node_data.get("slow", 26))
        signal = int(node_data.get("signal", 9))
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        sig_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line - sig_line  # histogram
    if indicator in ("close", "price"):
        return close
    # Default: SMA
    return close.rolling(period).mean()


def _apply_comparator(series: pd.Series, node_data: dict) -> pd.Series:
    """Apply a comparison operator to produce a boolean series."""
    op = node_data.get("op", "lt").lower()
    threshold = float(node_data.get("value", 50.0))

    if op in ("lt", "<"):
        return series < threshold
    if op in ("gt", ">"):
        return series > threshold
    if op in ("lte", "<="):
        return series <= threshold
    if op in ("gte", ">="):
        return series >= threshold
    if op == "crosses_above":
        return (series.shift(1) <= threshold) & (series > threshold)
    if op == "crosses_below":
        return (series.shift(1) >= threshold) & (series < threshold)
    # Default: less-than
    return series < threshold


class DynamicStrategy:
    """
    Evaluates a JSON node-graph into ``generate_signals(df)`` logic.

    Designed to be compatible with the Strategy protocol expected by
    ``VectorizedEngine``.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Parameters
        ----------
        config : dict
            Must contain "nodes" (list) and "edges" (list).
        """
        self.config = config
        self._validate(config)

    @staticmethod
    def _validate(config: dict) -> None:
        if "nodes" not in config or "edges" not in config:
            raise ValueError("Strategy config must contain 'nodes' and 'edges'")
        if not isinstance(config["nodes"], list):
            raise ValueError("config['nodes'] must be a list")
        if not isinstance(config["edges"], list):
            raise ValueError("config['edges'] must be a list")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Evaluate the node graph and return a signal series (+1, -1, 0).

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV DataFrame.

        Returns
        -------
        pd.Series with values in {-1, 0, 1}.
        """
        nodes = {n["id"]: n for n in self.config["nodes"]}
        # Build adjacency: node_id → list of successor ids
        children: dict[str, list[str]] = {n["id"]: [] for n in self.config["nodes"]}
        parents: dict[str, list[str]] = {n["id"]: [] for n in self.config["nodes"]}
        for edge in self.config["edges"]:
            src, tgt = edge["source"], edge["target"]
            if src in children:
                children[src].append(tgt)
            if tgt in parents:
                parents[tgt].append(src)

        # Topological evaluation cache
        cache: dict[str, pd.Series] = {}

        def evaluate(node_id: str) -> pd.Series:
            if node_id in cache:
                return cache[node_id]
            node = nodes[node_id]
            ntype = node.get("type", "")
            ndata = node.get("data", {})

            if ntype == "indicator":
                result = _compute_indicator(df, ndata)
            elif ntype == "comparator":
                parent_ids = parents[node_id]
                if parent_ids:
                    parent_series = evaluate(parent_ids[0])
                else:
                    parent_series = df["close"]
                result = _apply_comparator(parent_series, ndata).astype(float)
            elif ntype == "logic":
                op = ndata.get("op", "and").lower()
                parent_results = [evaluate(p) for p in parents[node_id]]
                if len(parent_results) == 0:
                    result = pd.Series(0.0, index=df.index)
                elif len(parent_results) == 1:
                    result = parent_results[0]
                elif op == "and":
                    result = parent_results[0]
                    for pr in parent_results[1:]:
                        result = result * pr  # boolean AND via multiplication
                else:  # OR
                    result = parent_results[0]
                    for pr in parent_results[1:]:
                        result = ((result + pr) > 0).astype(float)
            elif ntype in ("entry", "exit"):
                parent_results = [evaluate(p) for p in parents[node_id]]
                if parent_results:
                    result = parent_results[0]
                else:
                    result = pd.Series(0.0, index=df.index)
            else:
                result = pd.Series(0.0, index=df.index)

            cache[node_id] = result
            return result

        # Find entry nodes and build the final signal
        entry_nodes = [n for n in self.config["nodes"] if n.get("type") == "entry"]
        signals = pd.Series(0.0, index=df.index)

        for entry in entry_nodes:
            edata = entry.get("data", {})
            side = edata.get("side", "buy").lower()
            entry_signal = evaluate(entry["id"])
            if side == "buy":
                signals = signals.where(entry_signal <= 0, 1.0)
            elif side == "sell":
                signals = signals.where(entry_signal <= 0, -1.0)

        return signals.fillna(0.0)
