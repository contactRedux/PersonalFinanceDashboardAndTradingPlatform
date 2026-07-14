# Backend — The QuantNexus Server

## What is this folder?

This is the brain of the platform. When your browser asks "what is Apple's current price?" or "place a buy order for 10 shares," the code in this folder handles those requests, talks to the database, calls external APIs, and sends back answers.

Think of it like the kitchen in a restaurant. The dashboard (frontend) is the dining room where customers sit — but all the actual cooking happens here, out of sight.

The backend is built with **FastAPI** (Python) — a modern web framework that automatically generates interactive API documentation and handles many requests at the same time efficiently.

---

## Key Files

| File / Folder | What it does |
|---|---|
| `app/main.py` | The startup file — creates the FastAPI app, wires up all routes, connects Redis, starts the scheduler |
| `app/config.py` | Reads all environment variables from `.env` into a single typed settings object |
| `app/database.py` | Sets up the async connection to PostgreSQL/TimescaleDB |
| `app/api/` | All HTTP and WebSocket endpoints (see `app/api/README.md`) |
| `app/models/` | Database table definitions (see `app/models/README.md`) |
| `app/services/` | Business logic — market data, alerts, orders, sentiment (see `app/services/README.md`) |
| `app/tasks/` | Background jobs that run on a schedule (see `app/tasks/README.md`) |
| `app/schemas/` | Pydantic schemas — data validation shapes for API requests and responses |
| `app/middleware/` | Rate limiting (max 120 requests per minute per IP) |
| `app/auth/` | JWT (JSON Web Token — a small digitally-signed certificate that proves you're logged in) authentication |
| `migrations/` | Alembic database migration scripts — version-controlled changes to the database structure |
| `tests/` | pytest unit and integration tests |
| `main.py` | Entry point: `uvicorn app.main:app` |
| `pyproject.toml` | Python package dependencies and tool configuration |
| `Dockerfile` | Instructions to build the backend container image |

---

## Most Important Functions / Classes

**`create_app()`** in [`app/main.py`](app/main.py) — The factory function that builds the entire FastAPI application. It attaches CORS (Cross-Origin Resource Sharing — controls which websites can talk to this API), rate limiting, all routers, the health check endpoint, and Prometheus metrics.

**`lifespan()`** in [`app/main.py`](app/main.py) — Runs startup and shutdown logic: opens a Redis connection pool when the server starts, launches the data-refresh scheduler, and cleans up when the server stops.

**`get_settings()`** in [`app/config.py`](app/config.py) — Returns a cached settings object. Every other module calls this to read environment variables without duplicating parsing logic.

---

## How to Run Locally (without Docker)

```bash
cd backend

# Install dependencies using uv (a fast Python package manager)
uv sync

# Apply database migrations
uv run alembic upgrade head

# Start the development server with hot-reload
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.  
Interactive documentation: `http://localhost:8000/api/docs`

---

## How does this connect to the rest of the app?

- The **frontend** (`frontend/`) calls this backend's REST API endpoints and WebSocket feeds
- The **backtesting engine** (`backtesting/`) is imported directly inside the API endpoint handlers
- The **ML models** (`ml/`) are invoked by Celery tasks and by the `/api/v1/ml/` endpoints
- **TimescaleDB** stores all historical price bars; **Redis** caches the latest quotes; **MongoDB** stores news articles
- The **Celery worker** runs the same codebase but only processes background tasks (see `app/tasks/`)
