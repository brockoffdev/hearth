# Hearth — Project Plan & Spec

> **Working title:** `hearth`
> **Repo:** `/vagrant/hearth` (will be pushed to GitHub)
> **Plan author:** Claude (Opus 4.7), 2026-04-27
> **Status:** Draft v1 — pending user review and Claude Design UI pass

---

## 1. Context

Bryant and his wife share a physical wall calendar (whiteboard, dry-erase, ink-color-coded by family member) that hangs in their home. They both rely on it for day-to-day coordination, but they only see it when they're physically at home — and his wife is not comfortable with computer-based calendar tools.

**Hearth** is a self-hosted web service that bridges the wall calendar and Google Calendar. A family member snaps a photo of the wall calendar with their phone; the service parses the handwritten events, attributes each to the correct person by ink color, runs them through a confidence-threshold review, and pushes confirmed events to Google Calendar. The same service also drives a beautiful, glanceable wall-mounted "TV mode" display so anyone in the family can see what's coming up at a glance.

**Goal:** keep the wall calendar as the source of truth for in-the-home coordination, while making everything that's on it visible on every phone, every car dashboard, and every connected device the family uses — without making his wife learn anything new.

**Non-goals:**
- Replacing the physical wall calendar (it stays — that's the point).
- Multi-tenant SaaS. This is single-family, self-hosted.
- Real-time collaboration / shared editing. Photo → parse → publish is the only data-entry path.

---

## 2. Personas & Primary Use Cases

| Persona | Primary action | Where |
|---|---|---|
| **Photographer** (Bryant or wife) | Snaps a photo of the wall, uploads it. | Mobile phone, ~90% of uploads. |
| **Reviewer** (Bryant) | Reviews flagged events, edits, confirms. | Mobile *or* desktop. |
| **Family member at a glance** | Looks at the TV display to see "what's today / this week / what's coming." | Wall-mounted display in a common room. |
| **Admin** (Bryant) | Manages users, color→person mappings, Google Calendar settings. | Desktop. |

**Top three flows:**

1. **Capture flow** (mobile): home screen → tap "Upload" → camera or photo library → submit → wait → see results.
2. **Review flow**: review queue lists low-confidence events → tap one → edit form pre-populated with VLM guesses + the image crop showing what was read → confirm → push to Google Calendar.
3. **TV flow**: a tablet/old monitor on the wall opens `/tv` → cycles month → week → day → upcoming events → rinse and repeat.

---

## 3. Tech Stack (Recommendation)

| Layer | Choice | Rationale |
|---|---|---|
| **Backend** | **Python 3.12 + FastAPI** | Image-processing libraries (Pillow, OpenCV) are first-class. VLM ecosystem (transformers, Ollama clients) is native here. FastAPI gives async I/O for Google Calendar calls without ceremony. |
| **Frontend** | **React 19 + Vite + TypeScript** | Mature ecosystem for calendar UI components. Built once, served as static assets from FastAPI in production. |
| **Calendar UI lib** | **`schedule-x`** (or React Big Calendar fallback) | Lightweight, mobile-friendly, dual-view (month/week/day) out of the box. FullCalendar is heavier than we need. Final pick deferred to Claude Design. |
| **DB** | **SQLite** (single file, WAL mode) | Single-tenant, ≤10 writes/day. Zero ops. One-file backup. |
| **Auth** | **FastAPI-Users** + bcrypt + HttpOnly session cookies | Boring, well-trodden. Local users only. |
| **Google API** | **`google-auth-oauthlib` + `google-api-python-client`** | Official, stable. |
| **Image processing** | **OpenCV + Pillow** for preprocessing; **provider-pluggable VLM** for extraction (see §6) | Keeps the hard part swappable. |
| **Background jobs** | **FastAPI `BackgroundTasks`** — no Celery, no Redis | At ~10 photos/day max, an in-process worker is plenty. Upgrade path: drop in `arq` (Redis-based) without rewrites. |
| **Packaging** | **Single multi-stage Dockerfile** (amd64) | One image, one `docker compose up`. Mounts: `/data` (SQLite + uploaded images + state), `/config` (env, OAuth client secrets). |
| **CI** | GitHub Actions: lint (`ruff`), type-check (`mypy`, `tsc`), test (`pytest`, `vitest`), build image. | Standard. |

**Stacks considered and rejected:**

- *Node/TypeScript monolith* — second best. Image-processing libs adequate but never great; subprocess marshalling for a local VLM is awkward in the event loop. Pick this only if Bryant later decides the maintainer pool is more TS-fluent than Python-fluent.
- *Go monolith* — overkill for a home service; image-processing/VLM ergonomics are weak.
- *Polyglot (TS frontend + Python sidecar)* — splits debugging across two runtimes for no real win at this scale.
- *Rust* — would be fun, but "two devs and an LLM" maintainability suffers.

---

## 4. High-Level Architecture

```
┌─────────────────────────────── Browser ───────────────────────────────┐
│  Mobile (capture)        Desktop (review/admin)        TV (display)   │
└──────────────┬───────────────────────┬──────────────────────┬─────────┘
               │                       │                      │
               ▼                       ▼                      ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                   FastAPI (Python 3.12)                       │
        │                                                               │
        │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
        │  │  Auth   │  │ Uploads  │  │ Events   │  │ Calendar API │    │
        │  │ (sess.) │  │  + Jobs  │  │ + Review │  │  (Google)    │    │
        │  └─────────┘  └────┬─────┘  └──────────┘  └──────────────┘    │
        │                    │                                          │
        │                    ▼                                          │
        │            ┌───────────────────────┐                          │
        │            │ Vision Pipeline       │                          │
        │            │ ┌───────────────────┐ │                          │
        │            │ │ Preprocess (CV)   │ │                          │
        │            │ │ Cell segmentation │ │                          │
        │            │ │ VLM Provider*     │ │                          │
        │            │ │ Color → owner     │ │                          │
        │            │ │ Date normalize    │ │                          │
        │            │ │ Confidence gate   │ │                          │
        │            │ └───────────────────┘ │                          │
        │            └───────────────────────┘                          │
        │                                                               │
        │  ┌───────────────────────── SQLite ─────────────────────────┐ │
        │  │ users · family_members · uploads · events · corrections │ │
        │  │ · oauth_tokens · settings                               │ │
        │  └─────────────────────────────────────────────────────────┘ │
        └───────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                     ┌────────────────────────────┐
                     │   Google Calendar API      │
                     └────────────────────────────┘
```

**\* VLM Provider** is an interface (§6.3). v1 ships one or two implementations; others can be added without rewiring.

---

## 5. Web Surfaces (for Claude Design)

These are the screens Claude Design will mock up. Mobile-primary unless noted.

| Route | Purpose | Auth | Notes |
|---|---|---|---|
| `/setup` | First-run admin password change. Forces away from `admin/admin`. | Anonymous-but-bootstrap-only | Step 1 of first-run wizard. |
| `/setup/google` | First-run Google OAuth onboarding. Admin uploads OAuth client credentials (`client_id` + `client_secret`), maps the five Hearth family-member rows to existing Google Calendar IDs (or creates them via the API), and completes the OAuth consent round-trip. Until completed, all other routes redirect here. | Admin only | Step 2 of first-run wizard. See §8. Documentation link visible inline. |
| `/login` | Session login. | Anonymous | Username + password. |
| `/` | Home / dashboard. Shows recent uploads, queue depth, "next 7 days." | Auth | Mobile-first card layout. |
| `/upload` | Take photo or pick from library. Submit. Posts to `/api/uploads` and immediately redirects to `/uploads/:id`. | Auth | Uses `<input type="file" accept="image/*" capture="environment">` for mobile camera; falls back to gallery on desktop. |
| `/uploads/:id` | Two phases on the same route: (1) **processing screen** with live stage updates and a progress bar, then (2) **results screen** with the list of newly-extracted events grouped by status (auto-published vs queued for review), each linkable to its detail/edit page. | Auth | Live updates via SSE (`/api/uploads/:id/events`). See §6.5. |
| `/queue` | Review queue: list of events below confidence threshold. | Auth | Sorted by upload date desc, then date of event. |
| `/queue/:eventId` | Edit-and-publish form for a single event. Shows the cell crop next to the form. | Auth | Big buttons; designed for thumb-driven editing. |
| `/calendar` | Google-Calendar-style month/week/day view of all imported events. | Auth | Read-mostly; tap event → edit. |
| `/calendar/event/:id` | Edit existing event (already published). Saves push to Google Calendar. | Auth | Same form as `/queue/:eventId`, different "destination." |
| `/admin/users` | User CRUD. | Admin | Add, delete, reset password, change role. |
| `/admin/family` | Family-member CRUD: name, ink color (hex + label), target Google Calendar ID. | Admin | This is where "red = Mom, blue = Dad" lives. |
| `/admin/google` | Connect/reconnect Google account. Shows current OAuth status. | Admin | OAuth round-trip lives here. |
| `/admin/settings` | Confidence threshold slider, VLM provider config, default calendar. | Admin | |
| `/tv` | Wall display. Rotates month → week → day → upcoming. No header, no chrome. Auto-refresh. | **Open on the LAN** (see §10) | Designed for 1080p+ landscape; portrait variant via media query. |

**UX notes for Claude Design:**
- Color-coded chips for family members appear everywhere events are listed.
- Confidence is shown as a small percentage badge on review-queue items. Above-threshold events show a check-mark; below show a yellow "review" badge.
- "Today" is always emphasized on calendar views (background color + bold).
- TV view typography per industry conventions: sans-serif, ≥28pt body, ≥36pt time-of-day, glanceable from across the room.
- Every upload screen needs a clear progress indicator — parsing can take 5–60 seconds depending on provider.

---

## 6. Vision Pipeline (the hard part)

### 6.1 Stages

```
photo upload
   │
   ▼
[1] Preprocess          ─ EXIF rotation, downscale, deskew, perspective fix
   │                      (OpenCV: contour-detect outer rectangle of the
   │                       calendar frame, four-point transform)
   ▼
[2] Grid detect         ─ Find 5 weeks × 7 days; identify "notes" panel.
   │                      Hough lines or VLM-driven layout (one VLM call
   │                      with a "return cell bounding boxes" prompt).
   ▼
[3] Cell extraction     ─ Crop each cell + the right-hand notes panel.
   │
   ▼
[4] Per-cell VLM        ─ Send each non-empty cell to the VLM with a
   │                      structured prompt: return a JSON list of
   │                      events {title, time, color_hex, owner_guess,
   │                      confidence, raw_text}.
   ▼
[5] Color → owner       ─ For each event, dominant ink color (HSV
   │                      histogram of non-white pixels in the cell,
   │                      filtered to the bounding box of the recognized
   │                      text) → look up family_members table.
   ▼
[6] Date normalize      ─ Cell coords + month label → ISO date.
   │                      Multi-day arrows → infer end date.
   │                      "Eric →" arrows that span weeks → spans.
   ▼
[7] Confidence gate     ─ composite_confidence =
   │                        vision_conf × color_match_conf × date_conf
   │                      ≥ threshold (default 0.85): publish to GCal.
   │                      < threshold: insert into review queue.
   ▼
[8] Google Calendar     ─ For published events: insert via Calendar API.
   │                      Save google_event_id back to the row.
   ▼
[9] Notification        ─ Push UI update via Server-Sent Events; mobile
                          uploader sees "5 events found, 3 published, 2
                          queued" within seconds of the pipeline finishing.
```

### 6.2 Provider strategy: local-first, hosted as configurable fallback

Per user direction: **ship Ollama as the default v1 provider**, with Gemini and Anthropic as drop-in alternatives configurable from `/admin/settings`. No code rebuild required to switch.

**Hardware target:** **AMD Ryzen 9 7940HS** (8c/16t Zen 4) with a **Radeon 780M** integrated GPU (RDNA3, 12 CUs, gfx1103) and **64GB system RAM**. ROCm 6.0+ supports gfx1103, so the 780M can accelerate inference. Zen 4's AVX-512+VNNI also makes CPU fallback respectable.

**Resource budget (per user direction):**
- **Soft ceiling: ~8 GB** for the VLM model + working memory while a photo is being processed.
- **Lazy load:** the model is *not* resident by default. It loads on demand when a photo enters the pipeline and unloads as soon as the batch finishes.
- **Photo cadence: ~1–2 per week.** Cold-start latency is acceptable because inference is rare.

**Memory-budget vs model-size tradeoff:**

| Budget | Default model | Resident peak | Accuracy on this task | First-call load | Per-cell inference (iGPU) |
|---|---|---|---|---|---|
| 4 GB | Qwen2.5-VL 3B | ~2.7 GB | 75–80% | 8–15s | 4–10s |
| **8 GB** *(recommended)* | **Qwen2.5-VL 7B (Q4)** | ~5–6 GB | **80–85%** | 15–25s | 5–12s |
| 16 GB | Qwen3-VL 8B (Q4) or Qwen2.5-VL 7B (Q8) | ~9–10 GB | 82–86% | 25–40s | 7–15s |

The 4 → 8 GB step is the meaningful accuracy bump (~5 points). The 8 → 16 GB step buys only ~2 points and doubles load time. **Default to the 8 GB / Qwen2.5-VL 7B configuration**; users can dial down to the 3B if memory pressure becomes a problem, or up to the 16GB tier if they care about every percentage point.

**Lazy load / unload strategy** — Ollama supports a per-request `keep_alive` parameter:
- The Ollama call always passes `keep_alive: 0`, which causes the daemon to **unload the model immediately after the response finishes**.
- Inference flow: photo arrives → Ollama loads model (15–25s for 7B) → cell-by-cell generation (~5–12s/cell × N cells) → `keep_alive: 0` triggers immediate unload → 0 GB resident again.
- For a typical photo with ~15 populated cells: **load 20s + 15 inferences × 8s = ~140s wall-clock**, then memory returns to baseline.
- Across a week with 1–2 photos: total VLM-resident time per week is roughly 140–280 seconds. The 5–6 GB peak only exists during those windows.

**Settings exposed in `/admin/settings`:**
- `vlm_keep_alive_seconds` — default `0`. User can raise it (e.g. 300) if they're about to take several photos in quick succession.
- `vlm_max_concurrent_cells` — caps how many cells are dispatched in parallel (default 2 with the 8GB budget; raising it linearly increases peak memory).
- `vlm_model` — default `qwen2.5-vl:7b`. Pull-on-first-use. User can switch to `qwen2.5-vl:3b` for tighter memory or to a larger model for more accuracy without rebuilding the container.

**Hosted alternatives** (configurable, BYO key) — these have **zero local memory cost**, since they call out:
- **Gemini 2.5 Flash** — 87–94% accuracy on handwritten calendars, ~$0.001/image. ~10 photos/month = $0.01/month. Use when local accuracy isn't enough or you'd rather not load the model at all.
- **Anthropic Claude Haiku 4.5** — competitive cost, slightly behind Gemini on raw handwriting OCR. Sonnet 4.6 / Opus 4.7 available for hard-to-read entries.

**The user's "Claude Code instance on the container" idea** — interesting but adds a heavyweight agentic runtime for what is structurally a single API call. The same effect is achievable with the `anthropic` Python SDK directly, which is what `AnthropicProvider` will use. Keep this idea on the back burner.

**Hardware probe at startup:** the container detects whether ROCm is available and surfaces it in `/admin/settings`. If ROCm isn't usable, Ollama falls back to CPU — slower (15–30s/cell on Zen 4) but functional.

### 6.3 Provider abstraction

```python
# pseudo-Python
class VisionProvider(Protocol):
    name: str
    async def extract_events(
        self, cells: list[CellCrop], context: ExtractionContext
    ) -> list[ExtractedEvent]: ...
```

Three concrete implementations ship in v1:
1. `OllamaProvider` (**default**) — points at a local Ollama instance running Qwen2.5-VL 7B (configurable model name). The Ollama daemon runs as a sibling process inside the same Docker image, exposed on `localhost:11434`. Auto-detects ROCm at startup; uses the AMD iGPU if available, falls back to CPU otherwise. No external network needed.
2. `GeminiProvider` — uses `gemini-2.5-flash` via the official Python SDK. **Requires user-supplied API key.**
3. `AnthropicProvider` — uses `claude-haiku-4-5` by default, configurable to Sonnet 4.6 / Opus 4.7. **Requires user-supplied API key.**

Provider, model name, API key (where applicable), and Ollama endpoint URL are all configurable in `/admin/settings`. Switching providers does not require rebuilding the container.

**On packaging Ollama in the container:** two options on the table —
- **(a) Bundled** — Ollama daemon runs inside the same Docker image, with the chosen model pulled on first boot to a mounted volume. One image, one `docker compose up`. Larger image (~200MB base + the model on first run); simplest UX.
- **(b) Sidecar** — separate `ollama/ollama` container in `docker-compose.yml`, Hearth talks to it over the compose network. Cleaner separation; the user can update Ollama independently.

Recommendation: **(b) sidecar**, because it lets the user use the official Ollama image (with proper ROCm support baked in) and avoids us re-shipping their container build. Compose handles the orchestration.

### 6.4 The learning loop

When a user corrects a flagged event (or marks a published event as "wrong"):

1. The original VLM output, the user's correction, and a crop of the source cell get logged to the `event_corrections` table.
2. On subsequent uploads, the prompt sent to the VLM includes the **N most recent corrections** as few-shot examples ("Last week, you read 'Pikuagk Place' — the correct text was 'Pineapple Place.' Apply this kind of correction when you see similar handwriting.").
3. There's no model fine-tuning. Few-shot in-context examples are cheap, fast, and well within the input window for any of the supported providers.

This is intentionally simple. If accuracy plateaus, v2 can add embedding-based retrieval over the corrections table to pull the *most relevant* examples for each new photo.

### 6.5 Live progress reporting (SSE) — what the user sees on `/uploads/:id`

The pipeline emits named server-sent events as it advances. The processing screen subscribes to `/api/uploads/:id/events` and renders a checklist of stages with the active stage animated and earlier stages checkmarked.

| SSE event | UI label shown to the user | Notes |
|---|---|---|
| `received` | "Photo received." | Fired immediately on upload completion. |
| `preprocessing` | "Preparing image…" | EXIF rotation, downscale, deskew, perspective fix. ≤2s. |
| `grid_detected` | "Reading the calendar grid…" | Cell bounding boxes computed. |
| `model_loading` | "Loading vision model… (this can take 15–25 seconds the first time)" | Triggered on the first cell call when the model isn't already resident. Skipped on warm path. |
| `cell_progress` | "Reading cells… (3 of 15)" | One event per cell completion; UI updates a progress bar. |
| `color_matching` | "Identifying writers by ink color…" | Color → owner mapping. |
| `date_normalization` | "Resolving dates…" | Cell-coord → ISO date inference. |
| `confidence_gating` | "Reviewing confidence…" | Composite confidence applied; events sorted into auto-publish vs review-queue. |
| `publishing` | "Saving and publishing to Google Calendar…" | Auto-publish branch only. |
| `done` | "Done — *N* events found, *M* auto-published, *K* awaiting review" | Triggers UI transition to the results view. |
| `error` | "Something went wrong: \<message\>. Try again, or contact your admin." | Non-fatal stages can bubble up here without aborting the run. |

The **results view** that follows shows three lists, each as a stack of compact cards:
1. **Auto-published** (green check chip) — title, date/time, owner-color chip, link to the Google Calendar entry, "I was wrong" button (sends to edit page).
2. **Awaiting review** (yellow chip) — same fields, plus the cell crop, plus a confidence badge. "Review now" button → `/queue/:eventId`.
3. **Skipped / low-confidence rejected** (grey chip) — VLM thought it saw something but it's below the rejection floor. Listed for transparency; clickable to recover.

If `M = 0` and `K = 0` (no events at all), the results view shows a thoughtful empty state ("Nothing recognizable on the calendar yet — re-take the photo with brighter light or straighter angle?") with a "Re-upload" CTA.

### 6.6 Color → owner

Each row in `family_members` has:
- `name` (string)
- `color_hex_center` (e.g. `#D7263D` for red)
- `color_hue_range` (e.g. `hue ∈ [350, 10]` modulo 360 — automatically computed from `color_hex_center` with a ±15° default tolerance)
- `google_calendar_id` (string)

For each cell crop:
1. Mask out white-and-light pixels (V > 200 in HSV, or pixel `value > 200`).
2. Compute dominant hue of remaining pixels (peak of H histogram).
3. Match to the `family_members` row whose hue range contains the dominant hue.
4. Color match confidence = `1 - (distance from peak to nearest range center) / 90°`.

Edge cases (red and orange overlap, e.g.) are surfaced as low color-match confidence and force review.

---

## 7. Auth & User Management

- **Bootstrap:** on first container start, if no user exists, create `admin` with password `admin`, `must_change_password = TRUE`, and `must_complete_google_setup = TRUE`. Log a warning visible in container logs.

- **First-run wizard (admin only, ordered):**
  1. **Step 1 — `/setup`:** change username (optional) and password. Required before anything else. After submit, the user is logged in but immediately redirected to step 2.
  2. **Step 2 — `/setup/google`:** Google OAuth onboarding (see §8). The admin pastes their Google Cloud OAuth `client_id` and `client_secret` (created per the docs at `docs/google-oauth-setup.md`), then completes the OAuth consent round-trip. Once `oauth_tokens` row exists and the family-member calendar mapping is saved, `must_complete_google_setup` flips to `FALSE`.
  3. After step 2: redirect to `/`. The app is now fully usable.

- **Wizard gating:** while either flag is set on *any* admin (i.e., the only admin), every authenticated route except `/setup` / `/setup/google` / `/logout` redirects to the unfinished step. Anonymous routes still go through `/login`. Non-admin users cannot log in until the wizard is complete (the login page tells them "the admin hasn't finished setup yet").

- **Session model:** HttpOnly + `Secure` (when behind HTTPS) cookies, signed with a randomly-generated `SESSION_SECRET`. CSRF tokens on all state-changing endpoints.

- **Roles:** `admin` (everything) and `user` (everything except `/admin/*` and `/setup/*`). Both can upload, review, and edit events.

- **Admin actions:** create user, delete user, reset password, toggle role, re-run Google OAuth (e.g., to switch the connected account or recover from a token expiry).

- **Password storage:** bcrypt with default work factor (12).

---

## 8. Google Calendar Integration

- **v1 scope: one Google account, one family.** OAuth credentials and refresh token are stored once in `oauth_tokens`. All five Hearth family-member rows (Bryant, Danya, Izzy, Ellie, Family) point at calendars owned by this single connected account.
- **Future work (out of scope for v1):** multi-account support, where each family member could connect their own Google account and Hearth pushes events to *their* calendar instead of a shared owner's. This is a meaningful schema change (`oauth_tokens` becomes per-`family_member`, the OAuth refresh-and-store path duplicates) and we deliberately defer it.
- **OAuth flow:**
  1. Admin completes the manual prerequisite steps documented in `docs/google-oauth-setup.md`: create a Google Cloud project, enable the Calendar API, create an OAuth 2.0 Client ID (Desktop / Web — see docs for which), add an authorized redirect URI of `http(s)://<hearth-host>/api/google/oauth/callback`, and copy the `client_id` + `client_secret`.
  2. In `/setup/google`, the admin pastes those credentials. Hearth saves them to `settings` (`google_oauth_client_id`, `google_oauth_client_secret`).
  3. Hearth redirects the admin to Google for consent (`https://accounts.google.com/o/oauth2/v2/auth?...`) requesting scope `https://www.googleapis.com/auth/calendar`.
  4. Google redirects back to `/api/google/oauth/callback?code=…`. Hearth exchanges the code for an access + refresh token and persists to `oauth_tokens` (single-row table).
  5. Admin then maps each `family_members` row to a Google Calendar ID — either by picking from the list of calendars the API returns or by hitting "Create new calendar" which calls `calendars.insert`.
  6. After mapping is complete, `must_complete_google_setup` flips off.
- **Token refresh:** on any 401, Hearth uses the refresh token to mint a new access token and retries once. If the refresh token itself is invalid (e.g., 90-day inactivity expiry on consumer accounts, account password change, or revoked consent), surface a banner on `/` asking the admin to re-run `/setup/google`.
- **Event metadata pushed:** title, start/end (or all-day), description (with a footer like `Auto-imported by Hearth on 2026-04-27 from upload #42` for traceability), and an extended property `hearthEventId = <local id>` for round-trip linking.
- **Edits:** when a user edits an event from Hearth, the corresponding Google Calendar event is patched. If the Google event has been deleted out of band, Hearth detects the 410/404 and offers to recreate.
- **Deletes:** Hearth supports event deletion; it removes locally and calls Calendar `events.delete`.
- **Conflict policy:** if the same Hearth `events.id` already has a `google_event_id`, we patch. We do not de-dupe based on title/date heuristics — that's a future concern.

### 8.1 `docs/google-oauth-setup.md` (companion doc, written alongside the code)

This is a separate end-user document committed to the repo. Outline:

1. **Prerequisites** — a Google account; access to [console.cloud.google.com](https://console.cloud.google.com).
2. **Create a Google Cloud project** — step-by-step, screenshots welcome.
3. **Enable the Google Calendar API** — APIs & Services → Library → "Google Calendar API" → Enable.
4. **Configure the OAuth consent screen** — User type: External (for personal use); add yourself as a Test User; required scopes: `auth/calendar`.
5. **Create OAuth 2.0 Client ID credentials** — Application type: "Web application"; Authorized redirect URI: `http://hearth.local/api/google/oauth/callback` (or whatever hostname the user serves Hearth on). Copy the Client ID and Client Secret.
6. **Paste into Hearth `/setup/google`** — done; click "Connect" and complete the consent flow.
7. **Troubleshooting** — common errors (redirect URI mismatch, "app unverified" warning when used outside Test Users list, 90-day token expiry).

---

## 9. Data Model (SQLite)

```sql
users(
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','user')),
    must_change_password INTEGER NOT NULL DEFAULT 0,
    must_complete_google_setup INTEGER NOT NULL DEFAULT 0,  -- only ever set on the bootstrap admin
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

family_members(
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,                -- "Danielle", "Bryant", "Family"
    color_hex_center TEXT NOT NULL,           -- "#D7263D"
    hue_range_low INTEGER NOT NULL,           -- 350
    hue_range_high INTEGER NOT NULL,          -- 10
    google_calendar_id TEXT,                  -- nullable until connected
    sort_order INTEGER NOT NULL DEFAULT 0
);

uploads(
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    image_path TEXT NOT NULL,                 -- path inside /data/uploads/
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL CHECK (status IN ('queued','processing','completed','failed')),
    provider TEXT,                            -- e.g. "ollama:qwen2.5-vl:7b" or "gemini-2.5-flash"
    error TEXT,
    finished_at TIMESTAMP
);

events(
    id INTEGER PRIMARY KEY,
    upload_id INTEGER REFERENCES uploads(id),  -- nullable: hand-created events
    family_member_id INTEGER REFERENCES family_members(id),
    title TEXT NOT NULL,
    start_dt TIMESTAMP NOT NULL,
    end_dt TIMESTAMP,
    all_day INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    notes TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,     -- 0..1
    status TEXT NOT NULL CHECK (status IN
        ('pending_review','auto_published','published','rejected','superseded')),
    google_event_id TEXT,
    cell_crop_path TEXT,                       -- for review UI
    raw_vlm_json TEXT,                         -- audit trail
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

event_corrections(
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    before_json TEXT NOT NULL,                 -- VLM output
    after_json TEXT NOT NULL,                  -- user's correction
    cell_crop_path TEXT,
    corrected_by INTEGER NOT NULL REFERENCES users(id),
    corrected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

oauth_tokens(
    id INTEGER PRIMARY KEY CHECK (id = 1),     -- single row
    refresh_token TEXT NOT NULL,
    access_token TEXT,
    expires_at TIMESTAMP,
    scopes TEXT NOT NULL
);

settings(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Settings keys: confidence_threshold, vision_provider, vision_model,
-- vlm_keep_alive_seconds, vlm_max_concurrent_cells,
-- gemini_api_key, anthropic_api_key, ollama_endpoint,
-- google_oauth_client_id, google_oauth_client_secret, ...
```

---

## 10. TV Mode

- Route: `/tv` — fullscreen, no chrome.
- **Auth:** open on the LAN. The route is anonymous-accessible and intended for in-home use only. Any reverse-proxy / external-exposure setup is the operator's responsibility (Tailscale, VPN, etc.). If we later expose Hearth to the public internet, this is the first thing to revisit.
- **Layout:** four pages, rotating every 20 seconds:
  1. **Month** — current month grid, person-color-coded events.
  2. **Week** — current week, time-of-day axis, event blocks.
  3. **Day** — today's events, hour-by-hour.
  4. **Coming up** — list of all events more than ~7 days out, grouped by month.
- **Refresh:** events refresh from the API every 5 minutes via SSE. No flicker.
- **Responsive:** designed primarily for landscape 1080p; portrait variant via CSS.
- **Design language** (for Claude Design): editorial / "magazine on a wall" feel. Sans-serif, generous whitespace, large date type, clear color chips per family member, "TODAY" badge prominent on the current date.

---

## 11. Phased Roadmap

| Phase | Scope | Definition of Done |
|---|---|---|
| **0. Repo scaffold** | Dockerfile, FastAPI hello-world, Vite scaffold, SQLite + Alembic migrations, CI green. | `docker compose up` serves a "Hello, hearth" page on `:8080`. |
| **1. Auth & admin** | Bootstrap admin, login, `/setup` (password change), user CRUD, password hashing. | Bootstrap flow forces password change; a second user can be created and log in; admin can create/delete users. |
| **2. Google OAuth onboarding** | `/setup/google`, OAuth client creds intake, consent round-trip, calendar list+create, family-member→calendar mapping. Companion doc `docs/google-oauth-setup.md`. | Admin completes setup wizard end-to-end; `oauth_tokens` populated; family members mapped to real calendar IDs. Wizard gating works (other routes redirect until done). |
| **3. Family-member config (post-wizard editing)** | `/admin/family` CRUD; admin can edit colors/names/calendar mapping after setup. | Family members editable in admin UI; changes persist. |
| **4. Upload + image storage** | `/upload` mobile-friendly, file persisted, `uploads` row created, redirect to `/uploads/:id`. No parsing yet — processing screen shows static "Pipeline not yet implemented" state. | Can upload from a phone; image visible in `/uploads/:id` placeholder. |
| **5. Vision pipeline v0 (Ollama) + processing UI** | Compose Ollama sidecar; pull Qwen2.5-VL 7B; preprocess + grid-detect + per-cell VLM call + naive color match + naive date normalize. SSE stage events wired to the processing screen. Always queue for review (no auto-publish yet). | First end-to-end upload shows live progress on `/uploads/:id`, then transitions to results view with extracted events queued in `/queue`. |
| **6. Google Calendar push (review-queue path)** | Push from review-queue confirm action using the OAuth tokens established in phase 2. | Confirmed event appears in the correct Google Calendar within seconds. |
| **7. Confidence gate + auto-publish** | Composite confidence, threshold setting, auto-publish branch in pipeline + results view distinguishes auto-published from queued. | Above-threshold events go straight to GCal and show as auto-published in `/uploads/:id`; below-threshold queue. |
| **8. Calendar view + edit** | `/calendar`, `/calendar/event/:id` edit-and-push. | Round-trip: edit in Hearth → see change in Google Calendar. |
| **9. TV mode** | `/tv` four-page rotation (LAN-open), SSE refresh every 5min. | Wall display works on a tablet for 24h with no manual intervention. |
| **10. Learning loop** | `event_corrections` populated; few-shot prompt builder. | A correction made today is reflected in tomorrow's prompt. |
| **11. Hosted-provider expansion** | Add Gemini and Anthropic providers behind the same interface; runtime-switchable from `/admin/settings`. | Switching providers in `/admin/settings` works without restart. |

Phases 0–9 are the MVP. Phase 10 is the "gets better over time" promise. Phase 11 is for users who care about provider choice.

---

## 12. Decisions Locked In

These were resolved with the user before plan finalization:

1. **Vision provider:** **Ollama (local) is the v1 default**, with Gemini 2.5 Flash and Anthropic Claude (Haiku 4.5 / Sonnet 4.6 / Opus 4.7) as drop-in alternatives configurable from `/admin/settings`. Default Ollama model: **Qwen2.5-VL 7B (Q4)** with `keep_alive=0` lazy unload — peak resident memory ~5–6 GB during the 1–2 photo-processing windows per week, 0 GB the rest of the time. Hardware: Ryzen 9 7940HS + Radeon 780M (RDNA3, ROCm-supported). See §6.2.
2. **Calendar topology:** **Multi-calendar within one Google account** — one Google Calendar per family member (Bryant, Danya, Izzy, Ellie, Family), all owned by a single connected Google account. See §8.
3. **TV display auth:** **Open on the LAN.** No token, no login. See §10.
4. **Calendar lifecycle:** **Additive only.** Each photo adds events; nothing is auto-retired. The user can delete individual events from `/calendar` if needed. See §16 (Risks).

## 13. Defaults Chosen Without Asking

These were small enough that a default was applied; flag any you want changed before implementation:

- **Multi-day arrows** (e.g., "Eric →" spanning multiple days) are detected as multi-day events. Recurring/weekly events are *not* inferred from a single photo (too error-prone) — recurring schedules can be created manually in Google Calendar.
- **Image upload cap:** 10MB. Server downscales to 2048px on the long edge before VLM call.
- **Confidence threshold** default: 85%. User-tunable in `/admin/settings`.
- **Default few-shot correction window:** the most recent 10 corrections are appended to each VLM prompt. Tunable in settings.

---

## 14. Critical Files (for execution phase)

This plan does not yet write code, but for orientation when implementation begins, these are the files that will be created (paths relative to repo root `/vagrant/hearth`):

- `Dockerfile`, `docker-compose.yml`
- `pyproject.toml`, `uv.lock` (using `uv` for dependency mgmt)
- `backend/app/main.py` — FastAPI entry point
- `backend/app/auth/`, `backend/app/uploads/`, `backend/app/events/`, `backend/app/google/`, `backend/app/admin/`, `backend/app/tv/`
- `backend/app/setup/` — first-run wizard (`/setup`, `/setup/google`)
- `backend/app/vision/{pipeline.py, providers/{base.py, gemini.py, anthropic.py, ollama.py}, preprocessing.py, color.py, sse.py}`
- `backend/app/db/{models.py, migrations/}`
- `frontend/` — Vite + React + TS app
- `frontend/src/routes/{Login,Setup,SetupGoogle,Home,Upload,UploadDetail,Queue,Calendar,Admin,Tv}/`
- `frontend/src/components/{EventCard,FamilyChip,ConfidenceBadge,ProcessingStages,...}/`
- `tests/backend/`, `tests/frontend/`
- `docs/spec.md` — this document, committed once finalized
- `docs/google-oauth-setup.md` — end-user instructions for creating GCP OAuth credentials (see §8.1)
- `engram.yaml` — already exists

---

## 15. Verification Strategy

**End-to-end smoke test (manual, post-MVP):**

1. `docker compose up`. Visit `:8080`. See `/setup`. Change admin password.
2. Auto-redirected to `/setup/google`. Paste GCP OAuth credentials (created per `docs/google-oauth-setup.md`). Complete OAuth consent. Map the five family-member rows to Google Calendar IDs (creating any missing ones from the UI). Confirm wizard exits to `/`.
3. `/admin/family`: tweak colors / names if needed; verify changes persist.
4. `/upload` (mobile): submit a real photo of the wall calendar from a phone.
5. `/uploads/:id`: confirm the **processing screen** shows live SSE stages (`Photo received` → `Preparing image` → `Reading the calendar grid` → `Loading vision model` (first time only) → `Reading cells (X of N)` → `Identifying writers by ink color` → `Resolving dates` → `Reviewing confidence` → `Saving and publishing` → `Done`). Then transitions to results view showing the three lists (auto-published, awaiting review, skipped).
6. `/queue`: confirm low-confidence items show up; edit one; publish; verify it appears in the correct Google Calendar (the one mapped to that family member's ink color).
7. `/calendar`: confirm month/week/day views render and "today" is emphasized.
8. Open `/tv` on a separate LAN device (no auth required); confirm rotation and 5-min refresh.
9. Edit a previously-published event in `/calendar/event/:id`; confirm the change propagates to Google Calendar.
10. Make a correction in `/queue`; submit a second photo within a minute of the same area; confirm the correction shows up as a few-shot example in the second run's logged prompt.
11. Stop the container, observe RAM usage drops to baseline (no resident VLM after `keep_alive=0` unload).

**Automated tests:**

- `pytest`: unit tests for color matching, date normalization, confidence composition, OAuth token refresh, and provider stubs.
- `vitest`: component tests for review form, calendar event card, TV rotation logic.
- `pytest` integration: full pipeline run with a fixture image and a recorded VLM response (no live API in CI).

---

## 16. Notes for Claude Design

When this plan is loaded into Claude Design, the surfaces in §5 are the canvas. Specific things to design that aren't yet specified:

- **Color system & typography.** A warm, "home-y" palette that still reads cleanly. Not Material, not Bootstrap-default. Should pair well with the warm-and-fuzzy "hearth" name — think living room, not enterprise software.
- **The mobile upload experience.** This is the most-used surface. Should feel like Instagram-fast: tap, take photo, hit submit, see immediate feedback.
- **The processing screen** (`/uploads/:id` phase 1). A vertical checklist of stages (see §6.5 for the exact list) with the active stage animated, completed stages checkmarked, and an indeterminate progress bar inside the active row. Reassuring copy — the cold-load "Loading vision model" stage can take 15–25 seconds, so the screen must signal "this is normal, just wait." Smoothly transitions to the **results screen** (phase 2) on the `done` event.
- **The results screen** (`/uploads/:id` phase 2). Three sections, each a stack of cards: auto-published, awaiting review, skipped. Each card carries an owner-color chip, the event title/date, a confidence badge, and a primary action (open the Google Calendar entry, jump to review, etc.). Empty states explicitly handled.
- **The first-run wizard** (`/setup` → `/setup/google`). Two-step affair. Step 2 includes pasting credentials and clicking through to Google's consent screen — needs a clear "you're going to be redirected to Google" moment, plus a link to the setup doc for users who haven't created their GCP credentials yet.
- **The review queue card.** Each card needs: cell crop image, extracted fields with VLM guesses, confidence badge, family-member chip, big "Looks good" button, and an "Edit" affordance. Keep the decision-time under 5 seconds per item.
- **The TV view.** Editorial / magazine feel. Big date type, clear typography hierarchy, person-color chips, prominent "TODAY," graceful page transitions. Not a dashboard — a *poster*.
- **The admin panels.** Functional but not ugly. Inline editing where it makes sense.
- **Empty states.** Every list view needs a thoughtful empty state ("No uploads yet — take a photo of the wall calendar to get started").

---

## 17. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| VLM accuracy too low; review queue becomes a chore. | Local Qwen2.5-VL 7B starts at ~80%; tune confidence threshold via settings; few-shot learning loop bends the curve over time. If still unacceptable, switch the provider to Gemini 2.5 Flash from `/admin/settings` for a ~10% accuracy bump at ~$0.001/image. |
| Google OAuth refresh token expires (90 days inactive on consumer accounts). | Surface a banner on the dashboard when token health degrades; one-click reconnect. |
| Photo angle/perspective destroys grid detection. | OpenCV four-point transform handles up to ~30° skew; UI guides the user to align "frame in viewport" on capture. Worst case, fall back to "let the VLM see the whole photo and figure out the grid." |
| API key leakage. | Stored in `settings` table only, never logged. Admin-only routes. Optional env-var override for users who'd rather not put it in the DB. |
| TV display becomes unreliable (the "spouse acceptance factor" trap). | The TV route does its own state caching — last-known-good events render even if the API briefly goes away. Heartbeat indicator (small dot in the corner) shows freshness. |
| TV route is open on the LAN — anyone on the network can see the family schedule. | Acceptable for in-home use. If Hearth is later exposed beyond the LAN (Tailscale, reverse proxy, etc.), the operator must add their own auth layer in front of `/tv`. Documented in the README. |
| Local VLM accuracy lower than hosted alternatives. | Few-shot correction loop bends the curve over time. If accuracy stays unacceptable, switching to Gemini Flash is one settings change — no code rebuild. |
| AMD iGPU ROCm support is finicky on older APUs. | Container auto-falls-back to CPU if ROCm isn't usable. Detected and surfaced in `/admin/settings` so the user knows what's running. |
| Single point of failure: the home server. | Out of scope for v1. The whiteboard is still the source of truth; if the server is down, family life continues. |
