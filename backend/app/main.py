"""
QuantNexus — FastAPI application factory.

Entrypoint: uvicorn app.main:app
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.api.ws.router import ws_router
from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger(__name__)
settings = get_settings()


# ─── Lifespan: startup / shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise shared resources on startup; cleanly shut them down."""
    from app.data.cache.redis_client import close_redis_pool, get_redis_pool
    from app.data.ingestion.scheduler import start_scheduler, stop_scheduler

    logger.info("startup.begin", env=settings.app_env)
    await get_redis_pool()
    logger.info("startup.redis_ready")

    start_scheduler()
    logger.info("startup.scheduler_ready")

    yield  # Application runs

    stop_scheduler()
    await close_redis_pool()
    logger.info("shutdown.complete")


# ─── App factory ──────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    _app = FastAPI(
        title="QuantNexus API",
        description="Enterprise-grade algorithmic trading platform data service.",
        version="1.0.0",
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url="/api/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ─── CORS ─────────────────────────────────────────────────────────────────
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ─── Redis-backed per-IP rate limiting ────────────────────────────────────
    _app.add_middleware(RateLimitMiddleware)

    # ─── Validation error handler: return 422 with structured error detail ─────
    @_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    # ─── Generic error handler: never expose stack traces ─────────────────────
    @_app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please try again later."},
        )

    # ─── Routers ──────────────────────────────────────────────────────────────
    _app.include_router(api_v1_router, prefix="/api/v1")
    _app.include_router(ws_router)

    # ─── Health check ─────────────────────────────────────────────────────────
    @_app.get("/health", tags=["health"], include_in_schema=False)
    async def health() -> JSONResponse:
        """
        Always returns HTTP 200.  Individual service statuses are reported in
        the response body so callers can detect degraded-but-alive states without
        triggering load-balancer 5xx alarms.
        """

        async def _check_db() -> str:
            try:
                from app.database import engine  # noqa: PLC0415

                async with asyncio.timeout(1):
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                return "ok"
            except Exception:  # noqa: BLE001
                return "error"

        async def _check_redis() -> str:
            try:
                from app.data.cache.redis_client import get_redis_pool  # noqa: PLC0415

                async with asyncio.timeout(1):
                    redis = await get_redis_pool()
                    await redis.ping()
                return "ok"
            except Exception:  # noqa: BLE001
                return "error"

        async def _check_celery() -> str:
            try:
                import asyncio as _asyncio  # noqa: PLC0415

                from celery import Celery  # noqa: PLC0415

                async with asyncio.timeout(1):
                    celery_app = Celery(broker=settings.celery_broker_url)
                    inspect = celery_app.control.inspect(timeout=0.5)
                    # ping() is blocking — run in executor so we don't stall the loop
                    loop = _asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, inspect.ping)
                    celery_app.close()
                return "ok" if result else "error"
            except Exception:  # noqa: BLE001
                return "error"

        db_status, redis_status, celery_status = await asyncio.gather(
            _check_db(),
            _check_redis(),
            _check_celery(),
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "version": "1.0.0",
                "services": {
                    "database": db_status,
                    "redis": redis_status,
                    "celery": celery_status,
                },
            },
        )

    # ─── Prometheus metrics ───────────────────────────────────────────────────
    # Exposed at /metrics — scraped by Prometheus in docker-compose.
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,  # honour ENABLE_METRICS env var
        excluded_handlers=["/health"],
    ).instrument(_app).expose(_app, endpoint="/metrics", include_in_schema=False)

    return _app


app = create_app()
