"""
GET /fundamentals/{symbol}          — full fundamentals payload
GET /fundamentals/{symbol}/profile  — company profile only
GET /fundamentals/{symbol}/financials — income + balance + cashflow
GET /fundamentals/{symbol}/metrics  — key metrics + DCF
GET /fundamentals/{symbol}/earnings — earnings history + analyst estimates
GET /fundamentals/{symbol}/insiders — FMP insider transactions
GET /fundamentals/{symbol}/insider-flow — OpenInsider real-time Form 4 flow
GET /fundamentals/{symbol}/institutions — institutional holders
GET /fundamentals/{symbol}/earnings-transcript — EarningsCall.ai transcript list
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query

from app.config import get_settings
from app.dependencies import CurrentUser
from app.services.fundamentals.fmp import (
    build_demo_fundamentals,
    build_fundamentals_payload,
    get_analyst_estimates,
    get_balance_sheet,
    get_cash_flow,
    get_dcf,
    get_earnings_history,
    get_income_statement,
    get_insider_transactions,
    get_institutional_holders,
    get_key_metrics,
    get_profile,
)

router = APIRouter()
settings = get_settings()


def _no_key_response(symbol: str) -> dict:
    return build_demo_fundamentals(symbol)


@router.get("/{symbol}")
async def get_fundamentals(
    symbol: str = Path(..., description="Ticker symbol, e.g. AAPL"),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    """
    Full fundamentals payload for a symbol.

    Primary source: FMP (when FMP_API_KEY is configured).
    Secondary source: FactSet (when FACTSET_API_KEY is configured and FMP returns no data).
    Falls back to demo data when neither key is configured.
    """
    if not settings.fmp_api_key:
        # Try FactSet as secondary source
        if settings.factset_api_key:
            from app.services.fundamentals.factset import FactSetAdapter  # noqa: PLC0415
            factset = FactSetAdapter()
            profile = await factset.get_profile(symbol)
            if profile:
                financials = await factset.get_financials(symbol)
                estimates = await factset.get_estimates(symbol)
                return {
                    "symbol": symbol.upper(),
                    "source": "factset",
                    "profile": profile,
                    "financials": financials,
                    "estimates": estimates,
                }
        return _no_key_response(symbol)
    return await build_fundamentals_payload(symbol)


@router.get("/{symbol}/profile")
async def get_company_profile(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    profile = await get_profile(symbol)
    return {"symbol": symbol.upper(), "profile": profile}


@router.get("/{symbol}/financials")
async def get_financials(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    import asyncio  # noqa: PLC0415
    income, balance, cashflow = await asyncio.gather(
        get_income_statement(symbol),
        get_balance_sheet(symbol),
        get_cash_flow(symbol),
    )
    return {
        "symbol": symbol.upper(),
        "income_statement": income,
        "balance_sheet": balance,
        "cash_flow": cashflow,
    }


@router.get("/{symbol}/metrics")
async def get_metrics(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    import asyncio  # noqa: PLC0415
    metrics, dcf = await asyncio.gather(get_key_metrics(symbol), get_dcf(symbol))
    return {"symbol": symbol.upper(), "key_metrics": metrics, "dcf": dcf}


@router.get("/{symbol}/earnings")
async def get_earnings(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    import asyncio  # noqa: PLC0415
    history, estimates = await asyncio.gather(
        get_earnings_history(symbol),
        get_analyst_estimates(symbol),
    )
    return {
        "symbol": symbol.upper(),
        "earnings_history": history,
        "analyst_estimates": estimates,
    }


@router.get("/{symbol}/insiders")
async def get_insiders(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    data = await get_insider_transactions(symbol)
    return {"symbol": symbol.upper(), "insider_transactions": data}


@router.get("/{symbol}/institutions")
async def get_institutions(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    if not settings.fmp_api_key:
        return _no_key_response(symbol)
    data = await get_institutional_holders(symbol)
    return {"symbol": symbol.upper(), "institutional_holders": data}


@router.get("/{symbol}/insider-flow")
async def get_insider_flow_route(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
    days: int = Query(90, ge=1, le=365, description="Look-back window in days"),
) -> dict:
    """
    Real-time insider buy/sell flow from OpenInsider (free, no API key needed).
    Complements the FMP /insiders endpoint with up-to-date Form 4 data.
    """
    from app.services.news.aggregator import get_insider_flow  # noqa: PLC0415
    data = await get_insider_flow(symbol, days=days)
    return {"symbol": symbol.upper(), "insider_transactions": data, "days": days}


@router.get("/{symbol}/earnings-transcript")
async def get_earnings_transcript(
    symbol: str = Path(...),
    _: CurrentUser = ...,  # type: ignore[assignment]
    limit: int = Query(4, ge=1, le=12),
) -> dict:
    """
    Earnings call transcript list from EarningsCall.ai.
    Returns available transcripts (title, date, year, quarter).
    Use GET /fundamentals/{symbol}/earnings-transcript/{year}/{quarter} for full text.
    Falls back gracefully when EARNINGSCALL_API_KEY is not configured.
    """
    from app.services.news.earningscall import EarningsCallAdapter  # noqa: PLC0415
    adapter = EarningsCallAdapter()
    transcripts = await adapter.get_recent_transcripts(symbol, limit=limit)
    return {"symbol": symbol.upper(), "transcripts": transcripts}


@router.get("/{symbol}/earnings-transcript/{year}/{quarter}")
async def get_single_transcript(
    symbol: str = Path(...),
    year: int = Path(..., ge=2000, le=2100),
    quarter: int = Path(..., ge=1, le=4),
    _: CurrentUser = ...,  # type: ignore[assignment]
) -> dict:
    """Fetch the full text of a single earnings call transcript."""
    from app.services.news.earningscall import EarningsCallAdapter  # noqa: PLC0415
    adapter = EarningsCallAdapter()
    transcript = await adapter.get_transcript(symbol, year=year, quarter=quarter)
    if transcript is None:
        from fastapi import HTTPException, status  # noqa: PLC0415
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found for {symbol.upper()} Q{quarter} {year}",
        )
    return transcript
