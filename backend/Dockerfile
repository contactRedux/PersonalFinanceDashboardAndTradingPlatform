FROM python:3.11-slim-bookworm

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Install system-level dependencies:
#   - Build tools for packages that compile C/C++ extensions (hmmlearn, etc.)
#   - WeasyPrint runtime libs (pango, cairo, gdk-pixbuf)
#   - PyTorch OpenMP runtime (libgomp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi8 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

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

# Create ML weights directory owned by non-root user
RUN mkdir -p /app/data/ml_weights && chown -R 1001:1001 /app/data

USER 1001

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
