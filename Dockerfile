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

# gosu is used by the entrypoint to drop from root to the hearth user
# after fixing ownership of /data (named-volume init quirk).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=backend-builder /build/.venv /app/.venv

# Copy application source, Alembic migrations, and docs
COPY backend/ ./backend/
COPY alembic.ini ./
COPY docs/ ./docs/

# Copy built frontend from frontend-builder
COPY --from=frontend-builder /app/dist ./frontend/dist/

# Entrypoint that fixes /data ownership at runtime then drops to hearth.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create the data directory for the SQLite volume mount and non-root user.
# We do NOT set `USER hearth` — the entrypoint starts as root so it can
# chown /data (named volumes come up root-owned regardless of the image's
# baked-in ownership), then re-execs as hearth via gosu.
RUN mkdir -p /data && useradd -r -u 1001 hearth && chown -R hearth:hearth /app /data

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# --proxy-headers + --forwarded-allow-ips=* makes `request.base_url`
# reflect X-Forwarded-Proto / X-Forwarded-Host from any upstream
# reverse proxy (Tailscale Funnel, nginx, Cloudflare Tunnel, etc.),
# which is what makes the OAuth redirect_uri auto-detect work.
# Trust scope is "*": the operator is responsible for ensuring port
# 8080 is only reachable from the trusted proxy, not the open internet.
CMD ["python", "-m", "uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", "--port", "8080", "--log-level", "info", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
