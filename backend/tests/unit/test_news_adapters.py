"""
Unit tests — Reddit and SEC EDGAR news adapters (ST-AB).
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_praw_stub() -> ModuleType:
    """Build a minimal praw stub so the reddit adapter can be imported."""
    praw_stub = ModuleType("praw")
    praw_stub.Reddit = MagicMock  # type: ignore[attr-defined]
    sys.modules.setdefault("praw", praw_stub)
    return praw_stub


# ─── Reddit Adapter ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_reddit_returns_correct_keys_when_mocked():
    """Mocked PRAW response returns list with correct keys.

    praw is not installed in the test environment; we inject a stub into sys.modules
    so the lazy `import praw` inside _fetch_sync finds our mock instead.
    """
    # Build the submission mock
    submission = MagicMock()
    submission.title = "AAPL hits all time high"
    submission.permalink = "/r/stocks/comments/abc/aapl"
    submission.score = 42
    submission.created_utc = 1_700_000_000.0

    sub_mock = MagicMock()
    sub_mock.search.return_value = [submission]

    reddit_instance = MagicMock()
    reddit_instance.subreddit.return_value = sub_mock

    # Inject a praw stub that returns our mock instance
    praw_stub = _make_praw_stub()
    praw_stub.Reddit = MagicMock(return_value=reddit_instance)  # type: ignore[attr-defined]

    with patch.dict(sys.modules, {"praw": praw_stub}):
        from app.services.news.reddit import RedditAdapter  # noqa: PLC0415

        with patch("app.services.news.reddit.get_settings") as mock_settings:
            mock_settings.return_value.reddit_client_id = "fake_id"
            mock_settings.return_value.reddit_client_secret = "fake_secret"
            mock_settings.return_value.reddit_user_agent = "TestAgent/1.0"

            adapter = RedditAdapter()
            results = await adapter.get_news("AAPL", limit=5)

    assert isinstance(results, list)
    assert len(results) > 0
    item = results[0]
    assert "title" in item
    assert "url" in item
    assert item["source"] == "reddit"
    assert "subreddit" in item
    assert "score" in item
    assert "created_at" in item
    assert "sentiment" in item


@pytest.mark.anyio
async def test_reddit_missing_credentials_returns_empty():
    """When REDDIT_CLIENT_ID is absent, adapter returns []."""
    from app.services.news.reddit import RedditAdapter  # noqa: PLC0415

    with patch("app.services.news.reddit.get_settings") as mock_settings:
        mock_settings.return_value.reddit_client_id = ""
        mock_settings.return_value.reddit_client_secret = ""
        mock_settings.return_value.reddit_user_agent = ""

        adapter = RedditAdapter()
        adapter._settings = mock_settings.return_value
        results = await adapter.get_news("AAPL")

    assert results == []


# ─── SEC EDGAR Adapter ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_sec_edgar_returns_correct_keys_when_mocked():
    """Mocked httpx response returns list with correct keys."""
    from app.services.news.sec_edgar import SECEdgarAdapter  # noqa: PLC0415

    fake_response = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "form_type": "8-K",
                        "file_date": "2024-03-15",
                        "entity_name": "Apple Inc.",
                        "accession_no": "0000320193-24-000012",
                        "entity_id": "320193",
                    }
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = fake_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.services.news.sec_edgar.httpx.AsyncClient", return_value=mock_client):
        adapter = SECEdgarAdapter()
        results = await adapter.get_news("AAPL", limit=5)

    assert isinstance(results, list)
    assert len(results) == 1
    item = results[0]
    assert "title" in item
    assert "url" in item
    assert item["source"] == "sec_edgar"
    assert "form_type" in item
    assert "filed_at" in item
    assert "created_at" in item


@pytest.mark.anyio
async def test_sec_edgar_network_error_returns_empty():
    """On network error, SEC EDGAR adapter returns []."""
    import httpx  # noqa: PLC0415
    from app.services.news.sec_edgar import SECEdgarAdapter  # noqa: PLC0415

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))

    with patch("app.services.news.sec_edgar.httpx.AsyncClient", return_value=mock_client):
        adapter = SECEdgarAdapter()
        results = await adapter.get_news("AAPL")

    assert results == []
