# Hearth

> Self-hosted family wall-calendar to Google Calendar.
> Photo → preprocess → vision-model parse → ink-color attribution → confidence-gated review → Google Calendar.

The whiteboard stays the source of truth — Hearth is the loudspeaker that broadcasts it to every device in the house.

## Status

**Phase 2 of 10 — onboarding.**
The scaffold and design system are complete. Phase 2 adds local-account login and the first-run Google OAuth + calendar mapping wizard. See [docs/spec.md](docs/spec.md) for the full plan and [design_handoff_hearth/](design_handoff_hearth/) for the locked-in UI design.

## Quickstart

### Run via Docker (recommended)

```bash
# Generate and export a session secret first (required):
export HEARTH_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

docker compose up --build
# open http://localhost:8080/
```

The image bundles both the FastAPI backend and the built React frontend.

### Run locally for development

Two terminals:

#### Backend (port 8080)

```bash
uv sync
uv run uvicorn backend.app.main:app --reload --port 8080
```

#### Frontend (port 5173, with /api proxied to :8080)

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173/
```

Visit `/_design` to see every primitive in every theme.

## Tests

```bash
# backend
uv run pytest tests/backend/ -v

# frontend
cd frontend && npm run test

# everything (typecheck, lint, test)
uv run ruff check . && uv run mypy backend/ && uv run pytest tests/backend/
cd frontend && npm run lint && npm run typecheck && npm run test
```

## Configuration

The backend reads `HEARTH_*` environment variables. See `backend/app/config.py` for defaults and the available keys (debug, data_dir, frontend_dist_dir, cors_origins, session_cookie_secure). Override via env at runtime, e.g. `HEARTH_CORS_ORIGINS='["https://hearth.example.com"]'`.

For Google Calendar integration: see [docs/google-oauth-setup.md](docs/google-oauth-setup.md) for one-time GCP project + OAuth client setup (~10 min, only the admin needs to do this).

**Required:** `HEARTH_SESSION_SECRET` — a long random string used to sign session cookies. The application will refuse to start if this is not set. Generate one with:

```bash
export HEARTH_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

For production, provide this via a `.env` file, Docker secrets, or your deployment platform's secret store. Rotate periodically. Never commit a real value to the repository.

Set `HEARTH_SESSION_COOKIE_SECURE=true` in production (HTTPS). Default is `false` to allow HTTP in local development.

**Photo uploads:** `HEARTH_MAX_UPLOAD_BYTES` (default `26214400`, i.e. 25 MiB) caps the size of a single photo upload. Larger uploads return 413.

**Fake-pipeline timing (Phase 3 only):** `HEARTH_PIPELINE_STAGE_DELAY_SECONDS` (default `1.5`) and `HEARTH_PIPELINE_CELL_DELAY_SECONDS` (default `0.15`) control the simulated delays between SSE stage events. Phase 4 replaces the fake pipeline with real VLM inference, at which point these settings become irrelevant.

## Project layout

```
backend/             FastAPI app (Python 3.12, uv-managed)
frontend/            Vite + React 18 + TypeScript
tests/backend/       pytest suite for the backend
docs/spec.md         The project spec (read this before contributing)
design_handoff_hearth/   Design references (don't ship; lift tokens only)
pyproject.toml       Python project + tool config (ruff, mypy, pytest)
docker-compose.yml   Single-host deploy (Ollama VLM sidecar wired in for Phase 5)
.github/workflows/   CI (backend + frontend + docker smoke test)
```

## Roadmap

Phase 1 is complete. Phase 2 (onboarding) is in flight on this branch. Phases 3–10 follow:

1. Project scaffold + design system ✓
2. Onboarding: local-account login + first-run Google OAuth wizard ← we are here
3. Capture flow (mobile): home → camera → fake-progress processing
4. VLM pipeline backend (Ollama default, Gemini/Anthropic alternates)
5. Real SSE wiring (HEARTH_STAGES events on processing screen)
6. Results + review queue + single-item review
7. Google Calendar publish (auto-published items above 85% threshold)
8. Desktop calendar (editorial month) + Admin (family ↔ ink ↔ calendar mapping; provider/threshold settings)
9. TV mode (LAN-only, editorial layout)
10. States & polish (empty states, token-expired banner, theme toggle, dark/sepia)

> Note: this is a 10-phase rollup of [docs/spec.md §11](docs/spec.md), which lists 12 finer-grained phases. The shape is the same; the rollup matches how the implementation milestones are actually delivered.

See [docs/spec.md](docs/spec.md) for the detailed phase scope.

## Known limitations

Fonts (Fraunces, Inter, JetBrains Mono) are loaded from Google Fonts CDN; self-hosting them is a Phase 10 polish item.

## License

(TODO: pick a license before public release.)
