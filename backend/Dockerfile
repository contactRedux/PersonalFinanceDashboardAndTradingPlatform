FROM registry.redhat.io/ubi9/python-311-minimal:latest

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first (layer cache optimisation)
COPY pyproject.toml uv.lock* ./

# Install dependencies (no editable, no dev deps in production)
RUN uv sync --frozen --no-dev

# Copy application source
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser alembic.ini ./

USER 1001

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
