# ADR-001 — FastAPI + SQLAlchemy Async for the Backend API

**Date:** 2025-01-10  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The platform requires a Python backend capable of serving a real-time trading dashboard with
hundreds of concurrent WebSocket connections, sub-100 ms REST responses for quote and portfolio
data, and auto-generated interactive API documentation for frontend team integration. The team
evaluated three frameworks: Django (with Django REST Framework), Flask + SQLAlchemy sync, and
FastAPI + SQLAlchemy 2.0 async.

Django REST Framework was ruled out early: its synchronous ORM and WSGI heritage require
additional async shims (Django Channels, `asgiref`) to support WebSockets and concurrent I/O at
the scale needed. The ORM's ActiveRecord design also conflicts with the fine-grained query
control required for TimescaleDB hypertable operations and raw SQL time-series aggregations.

Flask + SQLAlchemy sync is familiar and low-overhead, but every blocking ORM call consumes a
thread. Under load (200 req/s target with 1,000 concurrent WebSocket connections), synchronous
I/O exhausts thread-pool capacity. Adding `asyncio` support to a sync Flask app produces a
hybrid that is harder to reason about than a natively async framework.

## Decision

Use **FastAPI** as the HTTP/WebSocket framework and **SQLAlchemy 2.0** with `asyncpg` as the
async database layer.

FastAPI is built on Starlette and Pydantic v2, giving native `async/await` throughout the
request lifecycle with zero extra wrappers. Its decorator-based router design mirrors Flask's
ergonomics, easing team adoption. Pydantic models serve as both request validation schemas and
OpenAPI schema sources, producing accurate interactive documentation at `/docs` with no extra
effort. SQLAlchemy 2.0's async session (`AsyncSession`) integrates cleanly with FastAPI's
dependency-injection system and supports raw SQL for TimescaleDB-specific queries.

## Consequences

### Positive
- All I/O (database, Redis, external APIs) runs on the event loop; no thread-pool bottlenecks
- OpenAPI documentation auto-generated at `/docs` (Swagger UI) and `/redoc`
- Pydantic v2 request/response validation with detailed error messages out of the box
- WebSocket handlers share the same event loop as REST handlers — no separate process needed
- SQLAlchemy 2.0 async supports both ORM-style queries and raw `text()` for complex SQL

### Negative
- `asyncio` discipline required throughout: any blocking call (CPU-intensive computation, sync
  library) must be wrapped with `asyncio.to_thread()` or delegated to a Celery worker
- SQLAlchemy async sessions are not thread-safe; the `scoped_session` pattern from sync code
  does not apply — team members must understand session lifecycle in async contexts
- FastAPI's dependency injection system has a learning curve compared to Flask's simpler model

### Neutral
- FastAPI does not bundle an ORM, admin panel, or user-auth module the way Django does;
  each concern (auth, migrations, admin) is added separately (Alembic, custom JWT, etc.)
- Uvicorn is the recommended ASGI server; Gunicorn with Uvicorn workers is used in production
