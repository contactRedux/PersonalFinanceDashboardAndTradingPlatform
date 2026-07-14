# ruff: noqa: E501

"""# ruff: noqa: UP042
Alert evaluator — compares current market data against alert conditions.

Alert types:
  - price_above   : price crosses above threshold
  - price_below   : price crosses below threshold
  - change_pct_gt : daily % change exceeds value
  - change_pct_lt : daily % change falls below value
  - volume_spike  : volume ratio vs 20-day avg exceeds threshold
  - pnl_below     : portfolio P&L falls below threshold (circuit breaker)

Alert lifecycle: pending → triggered → acknowledged
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum  # noqa: UP042
from typing import Any


class AlertType(str, Enum):  # noqa: UP042
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    CHANGE_PCT_GT = "change_pct_gt"
    CHANGE_PCT_LT = "change_pct_lt"
    VOLUME_SPIKE = "volume_spike"
    PNL_BELOW = "pnl_below"
    NEWS_KEYWORD = "news_keyword"


class AlertStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


@dataclass
class AlertCondition:
    alert_id: str
    user_id: str
    symbol: str | None  # None for portfolio-level alerts
    alert_type: AlertType
    threshold: float
    label: str
    status: AlertStatus = AlertStatus.PENDING
    created_at: str = ""
    triggered_at: str | None = None
    extra: dict[str, Any] | None = None


@dataclass
class AlertEvent:
    alert_id: str
    user_id: str
    symbol: str | None
    alert_type: str
    threshold: float
    actual_value: float
    label: str
    triggered_at: str
    message: str


def evaluate_price_alert(condition: AlertCondition, quote: dict[str, Any]) -> AlertEvent | None:
    """
    Evaluate a price-based alert against a live quote dict.
    Quote dict must have: price, change_pct, volume keys.
    Returns an AlertEvent if triggered, else None.
    """
    price = quote.get("price")
    change_pct = quote.get("change_pct")
    volume = quote.get("volume")

    if price is None:
        return None

    triggered = False
    actual_value = price

    if condition.alert_type == AlertType.PRICE_ABOVE and price > condition.threshold:
        triggered = True
    elif condition.alert_type == AlertType.PRICE_BELOW and price < condition.threshold:
        triggered = True
    elif condition.alert_type == AlertType.CHANGE_PCT_GT and change_pct is not None:
        actual_value = change_pct
        triggered = change_pct > condition.threshold
    elif condition.alert_type == AlertType.CHANGE_PCT_LT and change_pct is not None:
        actual_value = change_pct
        triggered = change_pct < condition.threshold
    elif condition.alert_type == AlertType.VOLUME_SPIKE and volume is not None:
        # volume_ratio must be pre-computed in quote dict
        ratio = quote.get("volume_ratio", 1.0)
        actual_value = ratio
        triggered = ratio > condition.threshold

    if not triggered:
        return None

    now = datetime.now(UTC).isoformat()
    symbol_str = condition.symbol or "PORTFOLIO"
    return AlertEvent(
        alert_id=condition.alert_id,
        user_id=condition.user_id,
        symbol=condition.symbol,
        alert_type=condition.alert_type.value,
        threshold=condition.threshold,
        actual_value=actual_value,
        label=condition.label,
        triggered_at=now,
        message=_build_message(condition, actual_value, symbol_str),
    )


def _build_message(
    condition: AlertCondition,
    actual_value: float,
    symbol_str: str,
) -> str:
    type_labels = {
        AlertType.PRICE_ABOVE: f"{symbol_str} crossed above ${condition.threshold:.2f} (now ${actual_value:.2f})",
        AlertType.PRICE_BELOW: f"{symbol_str} crossed below ${condition.threshold:.2f} (now ${actual_value:.2f})",
        AlertType.CHANGE_PCT_GT: f"{symbol_str} daily change {actual_value:+.2f}% exceeds +{condition.threshold:.2f}%",
        AlertType.CHANGE_PCT_LT: f"{symbol_str} daily change {actual_value:+.2f}% below {condition.threshold:.2f}%",
        AlertType.VOLUME_SPIKE: f"{symbol_str} volume ratio {actual_value:.1f}x exceeds {condition.threshold:.1f}x",
        AlertType.PNL_BELOW: f"Portfolio P&L ${actual_value:.2f} below threshold ${condition.threshold:.2f}",
        AlertType.NEWS_KEYWORD: f"News keyword alert for {symbol_str}",
    }
    return type_labels.get(condition.alert_type, condition.label)


def evaluate_all_alerts(
    conditions: list[AlertCondition],
    quotes: dict[str, dict[str, Any]],
) -> list[AlertEvent]:
    """
    Evaluate all pending alert conditions against a quotes snapshot.
    Returns list of triggered AlertEvents.
    """
    events: list[AlertEvent] = []
    for cond in conditions:
        if cond.status != AlertStatus.PENDING:
            continue
        if cond.symbol and cond.symbol in quotes:
            event = evaluate_price_alert(cond, quotes[cond.symbol])
            if event:
                events.append(event)
    return events
