# syntax=docker/dockerfile:1

# ---- Stage 1: frontend-builder ----
FROM node:24-slim AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend-builder ----
FROM python:3.12-slim AS backend-builder

WORKDIR /build

# Install uv
RUN pip install --no-cache-dir uv==0.11.8

COPY pyproject.toml uv.lock ./

# Install runtime deps only (no dev) into /build/.venv
RUN uv sync --no-dev --frozen --python python3.12

# ---- Stage 3: runner ----
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy virtual environment from builder
COPY --from=backend-builder /build/.venv /app/.venv

# Copy application source, Alembic migrations, and docs
COPY backend/ ./backend/
COPY alembic.ini ./
COPY docs/ ./docs/

# Copy built frontend from frontend-builder
COPY --from=frontend-builder /app/dist ./frontend/dist/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create the data directory for the SQLite volume mount and non-root user.
RUN mkdir -p /data && useradd -r -u 1001 hearth && chown -R hearth:hearth /app /data
USER hearth

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
