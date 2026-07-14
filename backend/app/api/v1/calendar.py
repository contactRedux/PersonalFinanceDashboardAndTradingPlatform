"""
Economic calendar endpoints — full implementation.

Returns upcoming and recent economic events with impact classifications.
Data source: Forex Factory-style events via FRED release calendar or
hardcoded demo events for UI development.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query

from app.dependencies import CurrentUser

router = APIRouter()


def _ev(
    eid: str,
    dt: str,
    time: str,
    impact: str,
    event: str,
    forecast: str | None = None,
    previous: str | None = None,
    actual: str | None = None,
    currency: str = "USD",
) -> dict:
    return {
        "id": eid,
        "date": dt,
        "time": time,
        "currency": currency,
        "impact": impact,
        "event": event,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
    }


_DEMO_EVENTS: list[dict] = [
    _ev("1", "2025-01-28", "10:00", "high", "CB Consumer Confidence", "105.5", "104.7"),
    _ev("2", "2025-01-29", "14:00", "high", "FOMC Interest Rate Decision", "5.50%", "5.50%"),
    _ev("3", "2025-01-29", "14:30", "high", "FOMC Press Conference"),
    _ev("4", "2025-01-30", "08:30", "high", "Advance GDP (Q4)", "2.6%", "3.1%"),
    _ev("5", "2025-01-30", "08:30", "medium", "Initial Jobless Claims", "220K", "217K"),
    _ev("6", "2025-01-31", "08:30", "high", "Core PCE Price Index (MoM)", "0.2%", "0.1%"),
    _ev("7", "2025-01-31", "09:45", "medium", "Chicago PMI", "45.2", "42.9"),
    _ev("8", "2025-02-03", "10:00", "medium", "ISM Manufacturing PMI", "48.5", "47.0"),
    _ev("9", "2025-02-05", "08:15", "high", "ADP Non-Farm Employment", "148K", "122K"),
    _ev("10", "2025-02-07", "08:30", "high", "Non-Farm Payrolls", "175K", "256K"),
    _ev("11", "2025-02-07", "08:30", "high", "Unemployment Rate", "4.1%", "4.1%"),
    _ev("12", "2025-02-12", "08:30", "high", "CPI (MoM)", "0.3%", "0.4%"),
    _ev("13", "2025-02-12", "08:30", "high", "Core CPI (MoM)", "0.3%", "0.3%"),
    _ev("14", "2025-02-13", "08:30", "high", "PPI (MoM)", "0.2%", "0.2%"),
    _ev("15", "2025-02-14", "08:30", "medium", "Retail Sales (MoM)", "0.1%", "-0.9%"),
    _ev("16", "2025-02-14", "10:00", "medium", "Michigan Consumer Sentiment", "72.8", "73.2"),
    _ev("17", "2025-02-19", "08:30", "medium", "Housing Starts", "1.35M", "1.50M"),
    _ev("18", "2025-02-20", "14:00", "high", "FOMC Meeting Minutes"),
    _ev("19", "2025-02-26", "08:30", "medium", "Durable Goods Orders (MoM)", "0.5%", "-1.1%"),
    _ev("20", "2025-02-28", "08:30", "high", "Core PCE Price Index (MoM)", "0.2%", "0.2%"),
]


@router.get("/events")
async def get_calendar_events(
    _: CurrentUser,
    start: str = Query(None, description="YYYY-MM-DD"),
    end: str = Query(None, description="YYYY-MM-DD"),
    impact: str = Query(None, description="high|medium|low or comma-separated"),
    currency: str = Query("USD", description="Currency filter"),
):
    """
    Return upcoming economic events filtered by date range and impact level.
    """
    today = date.today()
    start_date = date.fromisoformat(start) if start else today - timedelta(days=3)
    end_date = date.fromisoformat(end) if end else today + timedelta(days=30)

    impact_filter: set[str] | None = None
    if impact:
        impact_filter = {i.strip().lower() for i in impact.split(",")}

    events = []
    for event in _DEMO_EVENTS:
        event_date = date.fromisoformat(event["date"])
        if not (start_date <= event_date <= end_date):
            continue
        if event.get("currency", "USD") != currency.upper():
            continue
        if impact_filter and event["impact"] not in impact_filter:
            continue
        events.append(
            {
                **event,
                "is_upcoming": event_date >= today,
                "days_until": (event_date - today).days,
            }
        )

    events.sort(key=lambda e: (e["date"], e["time"]))
    return {
        "events": events,
        "count": len(events),
        "as_of": datetime.now(UTC).isoformat(),
        "note": "Demo calendar — integrate Forex Factory or Investing.com API for live data.",
    }
