"""
SEC EDGAR news adapter — fetches recent SEC filings for a ticker.

No API key required. Uses the public EDGAR full-text search API.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)

_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_TIMEOUT = 10.0


class SECEdgarAdapter:
    """Fetches recent SEC filings for a ticker via SEC EDGAR REST API."""

    async def get_news(self, ticker: str, limit: int = 5) -> list[dict]:
        """Return a list of SEC filing dicts for the given ticker.

        Each item: { title, url, source, form_type, filed_at, created_at }
        Returns [] on any error or timeout.
        """
        try:
            return await self._fetch(ticker, limit)
        except Exception:
            logger.exception("sec_edgar.fetch.error", ticker=ticker)
            return []

    async def _fetch(self, ticker: str, limit: int) -> list[dict]:
        params = {
            "q": f'"{ticker}"',
            "forms": "8-K,10-Q",
            "dateRange": "custom",
            "startdt": "2024-01-01",
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_EDGAR_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[dict] = []
        hits = data.get("hits", {}).get("hits", [])
        now_iso = datetime.now(UTC).isoformat()

        for hit in hits[:limit]:
            src = hit.get("_source", {})
            form_type = src.get("form_type", "")
            file_date = src.get("file_date", "")
            entity_name = src.get("entity_name", ticker)
            accession_no = src.get("accession_no", "").replace("-", "")

            # Build a URL to the filing index page
            url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar"
                f"?action=getcompany&filenum={accession_no}&type={form_type}"
                if not accession_no
                else f"https://www.sec.gov/Archives/edgar/data/"
                f"{src.get('entity_id', '')}/{accession_no}-index.htm"
            )

            results.append(
                {
                    "title": f"{entity_name} — {form_type} ({file_date})",
                    "url": url,
                    "source": "sec_edgar",
                    "form_type": form_type,
                    "filed_at": file_date,
                    "created_at": now_iso,
                }
            )

        return results
