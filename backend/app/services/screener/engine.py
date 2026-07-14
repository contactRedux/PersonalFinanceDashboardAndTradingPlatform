"""
Screener engine — fundamental + technical filter evaluation.

Supports a condition-based filter language where each condition is:
  { "field": "pe_ratio", "op": "lt", "value": 15 }

Supported operators: lt, lte, gt, gte, eq, neq, between
Supported field categories:
  - Fundamental: pe_ratio, pb_ratio, ps_ratio, market_cap, dividend_yield,
                 revenue_growth, eps_growth, profit_margin, debt_to_equity
  - Technical:   rsi_14, macd_signal, above_sma50, above_sma200, adx_14,
                 atr_pct, volume_ratio (vs 20-day avg), change_pct_1d
  - Metadata:    sector, exchange, asset_class
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── Operator helpers ─────────────────────────────────────────────────────────
_OPS = {
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "eq": lambda v, t: v == t,
    "neq": lambda v, t: v != t,
    "between": lambda v, t: isinstance(t, (list, tuple)) and len(t) == 2 and t[0] <= v <= t[1],
    "in": lambda v, t: isinstance(t, list) and v in t,
    "contains": lambda v, t: isinstance(v, str) and isinstance(t, str) and t.lower() in v.lower(),
}


@dataclass
class ScreenerCondition:
    field: str
    op: str
    value: Any

    def evaluate(self, row: dict[str, Any]) -> bool:
        """Return True if `row` satisfies this condition."""
        val = row.get(self.field)
        if val is None:
            return False
        fn = _OPS.get(self.op)
        if fn is None:
            return False
        try:
            return bool(fn(val, self.value))
        except (TypeError, ValueError):
            return False


@dataclass
class ScreenerRequest:
    conditions: list[ScreenerCondition] = field(default_factory=list)
    logic: str = "AND"  # "AND" or "OR"
    limit: int = 50
    sort_by: str = "market_cap"
    sort_desc: bool = True


@dataclass
class ScreenerResult:
    symbol: str
    name: str
    sector: str
    market_cap: float | None
    price: float | None
    change_pct_1d: float | None
    pe_ratio: float | None
    volume_ratio: float | None
    rsi_14: float | None
    fields: dict[str, Any]


class ScreenerEngine:
    """
    Evaluates a ScreenerRequest against a universe of symbols.
    Universe data is provided via `universe` — a list of symbol dicts
    with pre-computed fundamental and technical fields.
    """

    def run(
        self,
        request: ScreenerRequest,
        universe: list[dict[str, Any]],
    ) -> list[ScreenerResult]:
        """
        Filter `universe` rows against request conditions and return
        sorted, limited results.
        """
        results: list[ScreenerResult] = []

        for row in universe:
            if self._matches(row, request):
                results.append(self._to_result(row))

        # Sort
        results.sort(
            key=lambda r: getattr(r, request.sort_by, None) or 0,
            reverse=request.sort_desc,
        )
        return results[: request.limit]

    def _matches(self, row: dict[str, Any], req: ScreenerRequest) -> bool:
        if not req.conditions:
            return True
        if req.logic == "OR":
            return any(c.evaluate(row) for c in req.conditions)
        return all(c.evaluate(row) for c in req.conditions)

    @staticmethod
    def _to_result(row: dict[str, Any]) -> ScreenerResult:
        return ScreenerResult(
            symbol=row.get("symbol", ""),
            name=row.get("name", ""),
            sector=row.get("sector", ""),
            market_cap=row.get("market_cap"),
            price=row.get("price"),
            change_pct_1d=row.get("change_pct_1d"),
            pe_ratio=row.get("pe_ratio"),
            volume_ratio=row.get("volume_ratio"),
            rsi_14=row.get("rsi_14"),
            fields=row,
        )


def parse_screener_request(payload: dict[str, Any]) -> ScreenerRequest:
    """
    Parse a JSON payload into a ScreenerRequest.
    Payload shape:
    {
      "conditions": [{"field": "pe_ratio", "op": "lt", "value": 15}],
      "logic": "AND",
      "limit": 50,
      "sort_by": "market_cap",
      "sort_desc": true
    }
    """
    conditions = [
        ScreenerCondition(
            field=c["field"],
            op=c.get("op", "eq"),
            value=c["value"],
        )
        for c in payload.get("conditions", [])
        if "field" in c and "value" in c
    ]
    return ScreenerRequest(
        conditions=conditions,
        logic=payload.get("logic", "AND").upper(),
        limit=min(int(payload.get("limit", 50)), 200),
        sort_by=payload.get("sort_by", "market_cap"),
        sort_desc=bool(payload.get("sort_desc", True)),
    )
