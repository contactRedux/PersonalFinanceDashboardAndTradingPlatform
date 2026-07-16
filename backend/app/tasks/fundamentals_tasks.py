"""
Fundamentals refresh task — fetches FMP data and upserts into PostgreSQL.

Task:
  refresh_fundamentals(symbol) — fetch full FMP payload, upsert Fundamental row,
                                 bulk-insert latest insider transactions and
                                 institutional holders (idempotent via symbol+date).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _get_session_local():
    from app.database import AsyncSessionLocal as _asl  # noqa: PLC0415
    return _asl


# patchable alias for tests
try:
    from app.database import AsyncSessionLocal  # noqa: PLC0415
except Exception:  # noqa: BLE001
    AsyncSessionLocal = _get_session_local  # type: ignore[assignment, misc]


@celery_app.task(
    name="tasks.refresh_fundamentals",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def refresh_fundamentals(self, symbol: str) -> dict:
    """Fetch FMP fundamentals for symbol and upsert into the DB."""
    try:
        return asyncio.run(_refresh_fundamentals_async(symbol))
    except Exception as exc:  # noqa: BLE001
        backoff = 30 * (2 ** self.request.retries)
        logger.warning(
            "tasks.refresh_fundamentals.retry",
            symbol=symbol,
            retry=self.request.retries,
            backoff=backoff,
        )
        try:
            raise self.retry(exc=exc, countdown=backoff)
        except self.MaxRetriesExceededError:
            logger.error(
                "tasks.refresh_fundamentals.dead_letter",
                symbol=symbol,
                error=str(exc),
            )
            return {"symbol": symbol, "status": "failed", "error": str(exc)}


async def _refresh_fundamentals_async(symbol: str) -> dict:
    """Fetch FMP data and upsert into the database."""
    from app.config import get_settings  # noqa: PLC0415
    from app.models.fundamental import Fundamental, InsiderTransaction, InstitutionalHolder  # noqa: PLC0415
    from app.services.fundamentals.fmp import (  # noqa: PLC0415
        build_fundamentals_payload,
    )
    from sqlalchemy import select  # noqa: PLC0415

    settings = get_settings()
    if not settings.fmp_api_key:
        logger.info("tasks.refresh_fundamentals.no_key", symbol=symbol)
        return {"symbol": symbol, "status": "skipped", "reason": "FMP_API_KEY not configured"}

    payload = await build_fundamentals_payload(symbol)
    today = date.today()

    SessionLocal = AsyncSessionLocal  # noqa: N806

    async with SessionLocal() as session:
        # ── Upsert Fundamental row ────────────────────────────────────────────
        profile = payload.get("profile") or {}
        income = payload.get("income_statement") or [{}]
        balance = payload.get("balance_sheet") or [{}]
        metrics = payload.get("key_metrics") or [{}]
        dcf_data = payload.get("dcf") or {}

        latest_income = income[0] if income else {}
        latest_balance = balance[0] if balance else {}
        latest_metrics = metrics[0] if metrics else {}

        stmt = select(Fundamental).where(
            Fundamental.symbol == symbol.upper(),
            Fundamental.as_of_date == today,
        )
        result = await session.execute(stmt)
        row: Fundamental | None = result.scalar_one_or_none()

        if row is None:
            row = Fundamental(symbol=symbol.upper(), as_of_date=today)
            session.add(row)

        # Profile
        row.company_name = profile.get("companyName")
        row.sector = profile.get("sector")
        row.industry = profile.get("industry")
        row.description = (profile.get("description") or "")[:2000]
        row.exchange = profile.get("exchangeShortName")
        row.website = profile.get("website")
        row.employees = profile.get("fullTimeEmployees")
        row.beta = profile.get("beta")
        row.dividend_yield = profile.get("lastDiv")
        row.market_cap = profile.get("mktCap")

        # Income
        row.revenue_ttm = latest_income.get("revenue")
        row.net_income_ttm = latest_income.get("netIncome")
        row.gross_margin = latest_income.get("grossProfitRatio")
        row.operating_margin = latest_income.get("operatingIncomeRatio")
        row.eps_ttm = latest_income.get("eps")

        # Balance
        row.debt_equity = latest_balance.get("totalDebtToEquity")
        row.current_ratio = latest_balance.get("currentRatio")

        # Key metrics
        row.pe_ratio = latest_metrics.get("peRatio")
        row.pb_ratio = latest_metrics.get("pbRatio")
        row.ev_ebitda = latest_metrics.get("evToEbitda")
        row.dcf_value = dcf_data.get("dcf")

        row.updated_at = datetime.now(UTC)

        # ── Upsert insider transactions (last 20) ────────────────────────────
        insiders = payload.get("insider_transactions") or []
        for tx in insiders[:20]:
            filing_date_str = tx.get("transactionDate") or tx.get("filingDate") or str(today)
            try:
                filing_date = date.fromisoformat(filing_date_str[:10])
            except ValueError:
                filing_date = today

            insider_name = tx.get("reportingName") or tx.get("insiderName")
            shares_val = tx.get("securitiesTransacted")
            price_val = tx.get("price")

            # Skip if this exact (symbol, filing_date, insider_name) already exists
            check = await session.execute(
                select(InsiderTransaction).where(
                    InsiderTransaction.symbol == symbol.upper(),
                    InsiderTransaction.filing_date == filing_date,
                    InsiderTransaction.insider_name == insider_name,
                )
            )
            if check.scalar_one_or_none() is not None:
                continue

            session.add(InsiderTransaction(
                symbol=symbol.upper(),
                filing_date=filing_date,
                insider_name=insider_name,
                title=tx.get("typeOfOwner") or tx.get("title"),
                transaction_type=tx.get("transactionType"),
                shares=shares_val,
                price=price_val,
                value=float(shares_val or 0) * float(price_val or 0) if shares_val and price_val else None,
                shares_owned_after=tx.get("securitiesOwned"),
                sec_link=tx.get("link"),
            ))

        # ── Upsert institutional holders ─────────────────────────────────────
        institutions = payload.get("institutional_holders") or []
        for inst in institutions[:10]:
            filing_date_str = inst.get("dateReported") or str(today)
            try:
                filing_date = date.fromisoformat(filing_date_str[:10])
            except ValueError:
                filing_date = today

            holder_name = inst.get("holderName") or inst.get("holder")
            check = await session.execute(
                select(InstitutionalHolder).where(
                    InstitutionalHolder.symbol == symbol.upper(),
                    InstitutionalHolder.filing_date == filing_date,
                    InstitutionalHolder.holder == holder_name,
                )
            )
            if check.scalar_one_or_none() is not None:
                continue

            session.add(InstitutionalHolder(
                symbol=symbol.upper(),
                filing_date=filing_date,
                holder=holder_name,
                shares=inst.get("shares"),
                value=inst.get("value"),
                pct_portfolio=inst.get("weightPercent"),
                change=inst.get("change"),
            ))

        await session.commit()

    logger.info("tasks.refresh_fundamentals.done", symbol=symbol)
    return {"symbol": symbol, "status": "ok", "as_of": str(today)}
