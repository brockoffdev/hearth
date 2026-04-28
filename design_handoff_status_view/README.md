# Handoff: Hearth · Background-Processing Enhancement (v2)

> Adds a **MobileStatus inbox**, a **Continue-in-background** button on Processing, and a **live in-flight banner** on Home — relaxing the original "non-dismissible processing" constraint.

This is a sibling bundle to `design_handoff_hearth/`. Tokens, primitives, family palette, theme system, and Ember aesthetic are unchanged. Lift the new copy + interaction logic; re-author with CSS Modules per Phase-1 discipline.

---

## Why this enhancement

Real-world processing runs **60–120 seconds** on the target hardware (AMD Ryzen 9 7940HS / Radeon 780M / 64GB RAM, Qwen2.5-VL 7B at ~8s/cell × ~15 cells). Asking the user to sit and watch is too much — especially when the most common context is "snap a photo while making coffee."

**Backend behavior is unchanged.** The pipeline always runs to completion on the server. The frontend just gets a way to disengage and re-engage.

---

## Three surfaces

### 1. `MobileStatus` — the new "Uploads" inbox
**File:** `design/mobile-status-v2.jsx → MobileStatus`

Three sections, vertically:
- **In flight** (top) — accent-tinted card; spinner + current stage label (using `HEARTH_STAGES` vocabulary, e.g. `Reading cells · 12 of 35`); progress bar; ETA (`~3 min remaining`); thumbnail tile + start time. Tapping the row opens that upload's `MobileProcessing` screen.
- **Done** (middle) — neutral card; `{found} events found, {review} need review` + duration + finished-at. Tap → that upload's `Results`.
- **Couldn't read** (bottom) — danger-bordered card; error message; **Retry** button on the right.

Header reads either `"N processing · longest ~Xs remaining"` or `"All caught up · N recent"`. Pull-to-refresh hint sits inline. Tab bar uses `MobileTabBarV2` with `active="upload"`.

**Queued state** (artboard E): when 2+ uploads are submitted in quick succession, only one runs at a time on the GPU. The first row is the live one (spinner, real progress bar). Rows 2+ render with:
- A small **numbered position badge** (1/2/3) on the thumbnail
- Headline: `"Waiting · N photos ahead"` with a clock icon (not a spinner)
- A striped/empty progress bar instead of a live one
- ETA reads `total` (full pipeline + queue wait), not `remaining`
- The action affordance flips from "Open ↗" to "Cancel ×" since cancelling a queued (not-yet-started) row is cheap

**+ New capture sheet** (artboard F): a prominent gradient CTA at the top of the Status list. Tapping it presents a bottom sheet (with grabber, dim backdrop, slide-up animation) offering two options: **📷 Take a photo** (highlighted as primary) or **🖼 Choose from library**. Includes a small tip about lighting/handwriting.

### 2. `MobileProcessingV2` — Continue-in-background CTA
**File:** `design/mobile-status-v2.jsx → MobileProcessingV2`

Otherwise identical to the existing `MobileProcessing`. New additions:
- **Header subtext** under the title now shows live ETA: `"~3 min remaining · we'll let you know when it's done."`
- **Sticky bottom bar** with a primary `Continue in background` button + a small explanation: `"Keeps running on the server. Check back from Uploads."` Tapping the button navigates to `MobileStatus`. Pipeline keeps running — no API cancellation.
- Compacted vertical rhythm slightly so the new bottom bar fits without scroll on baseline iPhone heights.

### 3. `MobileHomeV2` — entry point + live banner
**File:** `design/mobile-status-v2.jsx → MobileHomeV2`

Two additions:
- **Live in-flight banner** — appears between the greeting and the upload CTA *only when* `inflightCount > 0`. Spinner + `"N photos processing… · ~Xs remaining"` + `"View →"`. Same accent treatment as Status's in-flight rows (visual continuity).
- **"View all uploads" link** at the bottom of the Home scroll — always present. Bright/bold when `inflightCount > 0`, muted (`var(--fgSoft)`) when quiescent. This gives the user a stable, predictable doorway to the Status inbox even when nothing's happening.

---

## API contract assumed

The frontend consumes these shapes — backend (Phase 4+) provides them:

```ts
// GET /api/uploads → list
type UploadStatus = 'processing' | 'completed' | 'failed';

interface Upload {
  id: string;
  status: UploadStatus;
  thumbLabel: string;       // human-readable timestamp e.g. "Apr 27, 8:38 AM"
  startedAt?: string;       // for processing
  finishedAt?: string;      // for completed/failed

  // processing-only
  current_stage?: string;            // a HEARTH_STAGES key
  completed_stages?: string[];       // ordered list of HEARTH_STAGES keys
  cellProgress?: number;             // present iff current_stage === 'cell_progress'
  totalCells?: number;
  remaining_seconds?: number;        // ETA from backend; frontend never computes
  queuedBehind?: number;             // 0 if running now; N if N pipelines ahead

  // completed-only
  found?: number;
  review?: number;
  durationSec?: number;

  // failed-only
  error?: string;
}

// GET /api/uploads/{id}/stream — SSE — stage events as before
// POST /api/uploads/{id}/retry — failed uploads only; creates a NEW upload (clean history)
```

ETA semantics (locked):
- Backend tracks **per-stage median duration** from completed runs.
- ETA = `Σ(median[stage] for stage in remaining_stages) + queue_wait`.
- `queue_wait = Σ(remaining_seconds of pipelines ahead in the queue)`.
- Phase 3 ships hard-coded medians; Phase 4 starts measuring real durations and improving over time.

---

## Locked design decisions

These were settled during the v2 review — don't relitigate:

1. **The Processing screen is no longer non-dismissible.** Continue-in-background dismisses it; the pipeline continues server-side. The original v1 spec said "non-dismissible — exiting kills the work." That is **superseded** by this v2.

2. **Tab bar: 4 tabs, "Upload" → "Uploads" (renamed and re-scoped).**
   The v1 tab bar had `Home · Upload · Review · Calendar` where "Upload" opened the camera directly. v2 keeps 4 tabs but renames the second slot to **Uploads** with a stack/list icon — tapping it opens `MobileStatus` (the inbox), not the camera.
   - Capture is now reached via a prominent **"+ New capture"** button at the top of the Status list, which presents a bottom sheet with **📷 Take a photo** and **🖼 Choose from library** options.
   - Why not 5 tabs (Upload + Status)? Tab bars read as *places to go to see things* (all nouns); injecting a verb-tab ("Upload") next to noun-tabs always feels off. Capture-as-a-sheet is more honest about what it is — a one-shot action — and frees the slot for the inbox, which is where users actually want to land.
   - Why not put capture on the Home upload-CTA only? It still is — Home's hero card kicks off a capture too. The sheet is the shared UI both Home's CTA and Status's "+ New capture" present.

3. **Tapping an in-flight row in Status opens `MobileProcessing` (full checklist).** Not a compact details view. Rationale: the checklist *is* the details view — re-using one component for both contexts is simpler than building two. Users who don't want the detail simply don't tap.

4. **Auto-refresh while in-flight items exist.** Frontend polls `/api/uploads` (or holds an SSE list-stream) on a 2–5 sec cadence whenever `inflightCount > 0`. Pull-to-refresh is also available. No optimistic animations on status flips — phone screens are small; just refresh in place.

5. **ETA factors in queue depth.** If 3 photos are queued, photo 3's ETA is its own pipeline + photos 1's + photo 2's remaining. Backend is responsible for this math. Frontend renders `remaining_seconds` verbatim. Queued (not-yet-running) photos display a "Waiting · N photos ahead" headline with a striped/empty progress bar instead of a live one.

6. **Retry creates a new upload row.** Clean history. The original failed row stays in the failed list as evidence. Backend: `POST /api/uploads/{id}/retry` returns the new upload's `id`.

7. **Home banner only appears when in-flight > 0.** When quiescent, the only entry point to Status is the muted `"View all uploads"` link at the bottom of the Home scroll. This keeps the home page calm by default.

8. **No notifications.** "We'll let you know when it's done" is aspirational copy, not a Phase-3 deliverable. Phase 5+ may add web-push or local notifications; out of scope here.

---

## Tokens / primitives — reuse only

No new colors, fonts, radii, or shadows. Everything resolves through:
- `var(--accent)`, `var(--success)`, `var(--warn)`, `var(--danger)` — semantic colors
- `var(--paper)`, `var(--paperDeep)`, `var(--bg)`, `var(--surface)` — backgrounds
- `var(--ink)`, `var(--fgSoft)`, `var(--rule)` — text & dividers
- `var(--fontDisplay)`, `var(--fontBody)`, `var(--fontMono)` — type
- `color-mix(in oklab, ...)` for soft tints (already used throughout v1)

Primitives reused: `PhoneShell`, `MobileTabBar`, `HBtn`, `HearthWordmark`, `FamilyChip`, `PhotoPlaceholder`. New tiny helpers (`Spinner`, `Chevron`, `BackChevron`, `ThumbTile`, `SectionRule`, `InflightRow`, `CompletedRow`, `FailedRow`) are local to `mobile-status-v2.jsx` — promote any of them to `primitives.jsx` if they end up used elsewhere.

---

## Files in this bundle

```
design_handoff_status_view/
├── README.md                          ← you are here
├── CLAUDE_CODE_PROMPT.md              ← copy-paste prompt for the implementation pass
└── design/
    ├── Hearth UI.html                 ← the canvas — section ⑧ "Background processing" is new
    ├── mobile-status-v2.jsx           ← MobileStatus + MobileProcessingV2 + MobileHomeV2 + helpers
    ├── tokens.js                      ← unchanged from v1; `HEARTH_UPLOADS_MOCK` is added by mobile-status-v2.jsx at runtime
    ├── primitives.jsx                 ← unchanged; reference only
    └── mobile-screens.jsx             ← unchanged; reference only
```

To view: open `design/Hearth UI.html` in any modern browser. Section ⑧ is the new content; everything else is unchanged from v1 for context.

---

## Diff summary for Claude Code

Implementer can think of this as four targeted changes against the Phase-3 implementation:

1. **New route `/uploads`** — renders `MobileStatus`. Tab-bar `Upload` icon now points here instead of (or in addition to) the camera flow — confirm with implementer; one option is the tab-bar opens Status and a FAB on Status opens the camera.
2. **New component `<UploadStatusList />`** with three sub-components for the row variants. Polls or subscribes to `/api/uploads`.
3. **`<MobileProcessing />` gains a sticky-bottom `<ContinueButton />`** + an ETA chip in the header. No SSE-cancellation logic; just navigation.
4. **`<MobileHome />` gains `<InflightBanner />`** (conditional on `inflightCount > 0`) and a permanent `<UploadsLink />` at the foot of the scroll.

State management: a single `useUploads()` hook that fans out the status list, the in-flight count, and the longest ETA. Same data source feeds Home banner, Status inbox, and Processing's ETA chip — single source of truth.

---

## Open questions for the implementer

1. **Notification surface** — out of scope for Phase 3, but the copy "we'll let you know when it's done" implies one. Decide before shipping whether to soften the copy or commit a Phase-5 push.
2. **Retry latency UX** — when user taps Retry on a failed row, does the new upload appear instantly with status `processing`, or do we wait for the API round-trip first? Recommend optimistic insert with rollback on error.
3. **Cancel on a queued (not-yet-started) row** — the queued artboard shows a "Cancel ×" affordance on rows that haven't begun running yet (cheap to drop them; nothing's been computed). For rows already running, the same affordance position shows "Open ↗" instead. Confirm backend supports `DELETE /api/uploads/{id}` on queued rows; running rows are not user-cancellable in this phase.
