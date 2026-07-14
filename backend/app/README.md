# backend/app — The FastAPI Application

## What is this folder?

This is where the FastAPI application lives — every piece of Python code that handles web requests, talks to databases, and runs business logic. If the `backend/` folder is the kitchen, this `app/` folder is where all the recipes and equipment are stored.

---

## Folder Structure

```
app/
├── main.py          Creates and configures the FastAPI app (start here)
├── config.py        All settings, read from environment variables
├── database.py      Async PostgreSQL connection pool
├── dependencies.py  Shared FastAPI "injectable" helpers (e.g. current user)
├── api/             HTTP and WebSocket route handlers
├── models/          SQLAlchemy ORM table definitions
├── schemas/         Pydantic request/response shapes
├── services/        Business logic (market data, alerts, orders, etc.)
├── tasks/           Celery background jobs
├── auth/            JWT token creation, verification, TOTP (two-factor auth)
├── data/            Cache helpers (Redis) and data ingestion (writers, normalizers)
└── middleware/      Rate limiting
```

---

## Request Lifecycle

Here is what happens when a user calls `GET /api/v1/market/quotes?symbols=AAPL`:

```
Browser → Nginx → FastAPI app (main.py)
  ↓
RateLimitMiddleware checks: has this IP exceeded 120 req/min?
  ↓
Route handler in app/api/v1/market.py
  ↓
dependencies.py: CurrentUser — verifies the JWT token, loads the user
  ↓
app/data/cache/quote_cache.py — check Redis for cached quote (< 60s old)
  ↓ (cache miss)
app/services/market_data/router.py — pick the configured data provider
  ↓
app/services/market_data/alpaca.py — call Alpaca REST API
  ↓
Response: {"quotes": {"AAPL": {"price": 192.40, ...}}}
```

---

## Most Important Files

**[`main.py`](main.py)** — The app factory (`create_app()`). This is the single entry point. It wires everything together: middleware, routers, error handlers, Prometheus metrics instrumentation.

**[`config.py`](config.py)** — A Pydantic `Settings` class that reads every environment variable in `.env`. All other modules call `get_settings()` instead of reading `os.environ` directly. This ensures all config is in one place and typed.

**[`database.py`](database.py)** — Sets up `AsyncSessionLocal` — an async PostgreSQL session factory. API handlers call `async with AsyncSessionLocal() as session:` to get a database connection.

**[`dependencies.py`](dependencies.py)** — Defines `CurrentUser`: a FastAPI dependency that extracts and verifies the JWT token from the `Authorization: Bearer ...` header and returns the logged-in user. Every protected endpoint declares `current_user: CurrentUser` in its signature.

---

## How does this connect to the rest of the app?

- **`api/`** is the public surface — everything the frontend or external clients call
- **`services/`** contains the actual work — `api/` handlers are thin wrappers that call into `services/`
- **`models/`** define what the database tables look like; `schemas/` define what API requests/responses look like (these are two separate things)
- **`tasks/`** run in a separate Celery worker process but share all the same service and model code
