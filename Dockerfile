# syntax=docker/dockerfile:1
# ---- Stage 1: build Python deps ----
FROM python:3.12-slim AS backend-builder

WORKDIR /build

# Install uv
RUN pip install --no-cache-dir uv==0.11.8

COPY pyproject.toml uv.lock ./

# Install runtime deps only (no dev) into /build/.venv
RUN uv sync --no-dev --frozen --python python3.12

# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy virtual environment from builder
COPY --from=backend-builder /build/.venv /app/.venv

# Copy application source
COPY backend/ ./backend/

# TODO (Task B): add frontend build stage and copy frontend/dist here:
# COPY --from=frontend-builder /frontend/dist ./frontend/dist/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
