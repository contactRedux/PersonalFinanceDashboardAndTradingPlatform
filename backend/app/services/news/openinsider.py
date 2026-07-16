"""
OpenInsider adapter — insider buy/sell signals from SEC Form 4 filings.

OpenInsider (https://openinsider.com) is a free public aggregator of SEC Form 4
filings. No API key required, no Terms of Service violation.

Data is fetched via the public screener CSV export endpoint and cached in Redis
(TTL 6 hours) to avoid hammering. Rate limited to 1 request/sec.
"""

from __future__ import annotations

import asyncio
import csv
import io
import time
from datetime import UTC, date, datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)

# OpenInsider CSV export — returns all Form 4 filings for a symbol
# Parameters: s=symbol, fd=-1 (all dates), td=-1, cnt=20 rows
_OPENINSIDER_URL = "https://openinsider.com/screener"
_CACHE_TTL = 60 * 60 * 6  # 6 hours
_MIN_INTERVAL = 1.0         # minimum seconds between requests (rate limit)
_TIMEOUT = 12.0

# Module-level rate limiter state
_last_request_at: float = 0.0
_lock: asyncio.Lock | None = None  # lazily created in the running event loop


def _get_lock() -> asyncio.Lock:
    global _lock  # noqa: PLW0603
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


# ─── Redis cache helpers ──────────────────────────────────────────────────────

async def _cache_get(key: str) -> str | None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        return await redis.get(key)
    except Exception:  # noqa: BLE001
        return None


async def _cache_set(key: str, value: str, ttl: int = _CACHE_TTL) -> None:
    try:
        from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415
        redis = await get_redis_pool()
        await redis.setex(key, ttl, value)
    except Exception:  # noqa: BLE001
        pass


# ─── Adapter ──────────────────────────────────────────────────────────────────

class OpenInsiderAdapter:
    """
    Fetches insider buy/sell transactions for a ticker from OpenInsider's
    public CSV export endpoint.

    Each returned item:
      filing_date, insider_name, title, transaction_type (P/S),
      shares, price, value, shares_owned_after, source="openinsider"
    """

    async def get_recent_trades(
        self,
        symbol: str,
        days: int = 90,
        limit: int = 20,
    ) -> list[dict]:
        """
        Return insider trades for `symbol` from the last `days` days.
        Returns [] on any error.
        """
        sym = symbol.upper()
        cache_key = f"openinsider:{sym}:{days}:{limit}"

        cached = await _cache_get(cache_key)
        if cached is not None:
            try:
                import json  # noqa: PLC0415
                return json.loads(cached)
            except (ValueError, Exception):  # noqa: BLE001
                pass

        try:
            rows = await self._fetch_csv(sym, limit)
        except Exception:  # noqa: BLE001
            logger.debug("openinsider.fetch_error", symbol=sym)
            return []

        result = [r for r in rows if self._within_days(r.get("filing_date", ""), days)]

        import json  # noqa: PLC0415
        await _cache_set(cache_key, json.dumps(result))
        return result

    async def _fetch_csv(self, symbol: str, limit: int) -> list[dict]:
        """Fetch and parse OpenInsider CSV for a symbol."""
        global _last_request_at  # noqa: PLW0603

        params = {
            "s": symbol,
            "fd": -1,
            "td": -1,
            "cnt": min(limit, 50),
            "action": "filter",
        }

        async with _get_lock():
            now = time.monotonic()
            wait = _MIN_INTERVAL - (now - _last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request_at = time.monotonic()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _OPENINSIDER_URL,
                params=params,
                headers={"Accept": "text/html,application/xhtml+xml"},
            )

        if resp.status_code != 200:
            logger.debug("openinsider.http_error", status=resp.status_code)
            return []

        # OpenInsider returns HTML. Extract the table rows using string parsing.
        # The data table starts after the first <table class="tinytable"> element.
        return self._parse_html_table(resp.text, symbol)

    def _parse_html_table(self, html: str, symbol: str) -> list[dict]:
        """
        Parse Form 4 rows from OpenInsider HTML response.
        Falls back to empty list if the expected table is not found.
        """
        now_iso = datetime.now(UTC).isoformat()
        results = []

        try:
            # Find the data table — OpenInsider uses a consistent table with class="tinytable"
            # Rows format: Filing Date | Trade Date | Ticker | Insider | Title | Trade Type | Price | Qty | Owned | ΔOwn | Value
            table_start = html.find('class="tinytable"')
            if table_start == -1:
                return []

            tbody_start = html.find("<tbody>", table_start)
            tbody_end = html.find("</tbody>", tbody_start)
            if tbody_start == -1 or tbody_end == -1:
                return []

            tbody = html[tbody_start:tbody_end]

            # Extract rows
            row_start = 0
            while True:
                tr_start = tbody.find("<tr", row_start)
                if tr_start == -1:
                    break
                tr_end = tbody.find("</tr>", tr_start)
                if tr_end == -1:
                    break

                row_html = tbody[tr_start:tr_end + 5]
                row_start = tr_end + 5

                cells = self._extract_cells(row_html)
                if len(cells) < 10:
                    continue

                # Column indices (0-based):
                # 0: Filing Date, 1: Trade Date, 2: Ticker, 3: Insider Name,
                # 4: Title, 5: Trade Type, 6: Price, 7: Qty, 8: Owned, 9: ΔOwn, 10: Value
                filing_date = cells[0].strip()
                insider_name = cells[3].strip()
                title = cells[4].strip()
                trade_type_raw = cells[5].strip().lower()
                price_raw = cells[6].replace("$", "").replace(",", "").strip()
                qty_raw = cells[7].replace(",", "").replace("+", "").strip()
                owned_raw = cells[8].replace(",", "").strip()
                value_raw = cells[10].replace("$", "").replace(",", "").replace("+", "").strip()

                # Classify transaction type
                if "p - purchase" in trade_type_raw or trade_type_raw.startswith("p"):
                    transaction_type = "P"
                elif "s - sale" in trade_type_raw or trade_type_raw.startswith("s"):
                    transaction_type = "S"
                else:
                    transaction_type = trade_type_raw[:10]

                try:
                    price = float(price_raw) if price_raw else None
                except ValueError:
                    price = None

                try:
                    shares = float(qty_raw) if qty_raw else None
                except ValueError:
                    shares = None

                try:
                    shares_owned = float(owned_raw) if owned_raw else None
                except ValueError:
                    shares_owned = None

                try:
                    value = float(value_raw) if value_raw else None
                except ValueError:
                    value = None

                results.append({
                    "symbol": symbol,
                    "filing_date": filing_date[:10] if filing_date else "",
                    "insider_name": insider_name,
                    "title": title,
                    "transaction_type": transaction_type,
                    "shares": shares,
                    "price": price,
                    "value": value,
                    "shares_owned_after": shares_owned,
                    "source": "openinsider",
                    "created_at": now_iso,
                })

        except Exception:  # noqa: BLE001
            logger.debug("openinsider.parse_error", symbol=symbol)
            return []

        return results

    def _extract_cells(self, row_html: str) -> list[str]:
        """Extract text content from all <td> cells in a row."""
        cells = []
        pos = 0
        while True:
            td_start = row_html.find("<td", pos)
            if td_start == -1:
                break
            td_content_start = row_html.find(">", td_start) + 1
            td_end = row_html.find("</td>", td_content_start)
            if td_end == -1:
                break
            raw = row_html[td_content_start:td_end]
            # Strip HTML tags
            text = ""
            in_tag = False
            for ch in raw:
                if ch == "<":
                    in_tag = True
                elif ch == ">":
                    in_tag = False
                elif not in_tag:
                    text += ch
            cells.append(text.strip())
            pos = td_end + 5
        return cells

    @staticmethod
    def _within_days(filing_date_str: str, days: int) -> bool:
        """Return True if the filing date is within the last N days."""
        if not filing_date_str:
            return True  # include when date unknown
        try:
            fd = date.fromisoformat(filing_date_str[:10])
            return (date.today() - fd).days <= days
        except ValueError:
            return True
