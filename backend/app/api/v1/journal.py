"""
Journal REST endpoints.

Fetches AI-generated trade journal entries from MongoDB trade_journal collection.
Falls back to empty list when MongoDB is unavailable.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("")
async def get_journal(current_user: CurrentUser):
    """Return AI trade journal entries for the authenticated user."""
    user_id: str = current_user["sub"]
    try:
        import motor.motor_asyncio  # noqa: PLC0415

        from app.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
        db = client[settings.mongodb_database]
        cursor = db.trade_journal.find(
            {"user_id": user_id},
        ).sort("created_at", -1).limit(50)
        entries = []
        async for doc in cursor:
            doc.pop("_id", None)
            entries.append(doc)
        return {"entries": entries, "count": len(entries)}
    except Exception:  # noqa: BLE001
        logger.warning("journal.mongodb_unavailable", user_id=user_id)
        return {"entries": [], "count": 0}
