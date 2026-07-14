"""
MongoDB index initialization script.

Run with:
    cd backend && uv run python -m scripts.init_mongodb_indexes

Or during Docker startup via the backend's lifespan (if MongoDB is available).
"""
from __future__ import annotations

import asyncio

import motor.motor_asyncio
import structlog

logger = structlog.get_logger(__name__)


async def create_indexes(mongo_url: str, db_name: str) -> None:
    """Create all MongoDB indexes for the QuantNexus collections."""
    client: motor.motor_asyncio.AsyncIOMotorClient = (
        motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    )
    db = client[db_name]

    # ─── news_articles collection ─────────────────────────────────────────────
    articles = db["news_articles"]

    # Uniqueness: prevent duplicate ingestion of the same article
    await articles.create_index(
        [("source", 1), ("source_id", 1)], unique=True, sparse=True
    )
    # Query by ticker symbol (most common access pattern)
    await articles.create_index([("tickers_mentioned", 1)])
    # Time-range queries for news feed pagination
    await articles.create_index([("published_at", -1)])
    # Filter by sentiment label + time
    await articles.create_index([("sentiment.label", 1), ("published_at", -1)])
    # Filter by impact category
    await articles.create_index([("sentiment.impact_category", 1)])

    logger.info("mongodb.index.created", collection="news_articles")

    # ─── ticker_sentiment_aggregate collection ────────────────────────────────
    aggregates = db["ticker_sentiment_aggregate"]

    # Primary lookup: one document per symbol
    await aggregates.create_index([("symbol", 1)], unique=True)
    # Sort by updated time for cache invalidation queries
    await aggregates.create_index([("updated_at", -1)])

    logger.info("mongodb.index.created", collection="ticker_sentiment_aggregate")

    client.close()
    logger.info("mongodb.indexes.all_done")


async def main() -> None:
    import os

    from dotenv import load_dotenv

    load_dotenv()

    mongo_url = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DATABASE", "quantnexus")

    logger.info("mongodb.init_indexes.start", url=mongo_url, db=db_name)
    await create_indexes(mongo_url, db_name)


if __name__ == "__main__":
    asyncio.run(main())
