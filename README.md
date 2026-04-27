# Hearth

> Self-hosted family wall-calendar to Google Calendar.
> Photo → preprocess → vision-model parse → ink-color attribution → confidence-gated review → Google Calendar.

The whiteboard stays the source of truth — Hearth is the loudspeaker that broadcasts it to every device in the house.

## Status

**Phase 1 of 10 — scaffold + design system.**
The skeleton runs but has no business logic yet (no upload, no VLM pipeline, no Google Calendar integration). See [docs/spec.md](docs/spec.md) for the full plan and [design_handoff_hearth/](design_handoff_hearth/) for the locked-in UI design.

## Quickstart

### Run via Docker (recommended)

```bash
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

The backend reads `HEARTH_*` environment variables. See `backend/app/config.py` for defaults and the available keys (debug, data_dir, frontend_dist_dir, cors_origins). Override via env at runtime, e.g. `HEARTH_CORS_ORIGINS='["https://hearth.example.com"]'`.

## Project layout

```
backend/             FastAPI app (Python 3.12, uv-managed)
frontend/            Vite + React 18 + TypeScript
docs/spec.md         The project spec (read this before contributing)
design_handoff_hearth/   Design references (don't ship; lift tokens only)
docker-compose.yml   Single-host deploy (Ollama VLM sidecar wired in for Phase 5)
```

## Roadmap

Phase 1 (scaffold + design system) is in flight on this branch. Phases 2–10 follow:

1. Project scaffold + design system ← we are here
2. Onboarding: local-account login + first-run Google OAuth wizard
3. Capture flow (mobile): home → camera → fake-progress processing
4. VLM pipeline backend (Ollama default, Gemini/Anthropic alternates)
5. Real SSE wiring (HEARTH_STAGES events on processing screen)
6. Results + review queue + single-item review
7. Google Calendar publish (auto-published items above 85% threshold)
8. Desktop calendar (editorial month) + Admin (family ↔ ink ↔ calendar mapping; provider/threshold settings)
9. TV mode (LAN-only, editorial layout)
10. States & polish (empty states, token-expired banner, theme toggle, dark/sepia)

See [docs/spec.md](docs/spec.md) for the detailed phase scope.

## Known limitations

Fonts (Fraunces, Inter, JetBrains Mono) are loaded from Google Fonts CDN; self-hosting them is a Phase 10 polish item.

## License

(TODO: pick a license before public release.)
