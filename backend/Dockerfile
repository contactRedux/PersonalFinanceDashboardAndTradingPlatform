FROM registry.redhat.io/ubi9/python-311-minimal:latest

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Install system-level dependencies required by WeasyPrint (PDF rendering)
# and by PyTorch (libgomp for OpenMP parallelism).
# ubi9-minimal ships with microdnf.
RUN microdnf install -y \
    pango \
    cairo \
    cairo-gobject \
    gdk-pixbuf2 \
    libffi \
    libgomp \
    && microdnf clean all

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
