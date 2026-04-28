# Claude Code prompt — Hearth v2 (Background processing)

Run this *after* Phase 1–2 of `design_handoff_hearth/` are merged. It can either fold into the Phase 3 implementation (cleanest) or land as a v2 patch immediately following Phase 3.

The `design_handoff_status_view/` folder must be present at the repo root before you start.

---

## Copy-paste this into Claude Code

```
You are implementing the Background-Processing enhancement to Hearth's capture flow. The full enhancement spec is in ./design_handoff_status_view/.

START BY READING (in this order):
  1. ./design_handoff_status_view/README.md                    — what's changing, why, locked decisions
  2. ./design_handoff_status_view/design/mobile-status-v2.jsx  — MobileStatus, MobileStatusQueued, MobileProcessingV2, MobileHomeV2, MobileTabBarV2, NewCaptureSheet
  3. ./design_handoff_status_view/design/Hearth UI.html        — open in a browser; section ⑧ "Background processing" has 6 artboards covering every state
  4. ./design_handoff_hearth/README.md                         — original v1 spec, for context this enhancement modifies

CONTEXT FROM v1 (already shipped or in-flight):
  Phase 1 (scaffold + tokens + primitives)             — DONE
  Phase 2 (login + first-run Google OAuth)             — DONE
  Phase 3 (Home → Camera → Processing → Results)       — IN PROGRESS or just merged

  ⚠ THE v1 RULE THIS ENHANCEMENT EXPLICITLY SUPERSEDES:
    v1 said: "Processing screen is non-dismissible — exiting kills the work."
    v2 says: Processing IS dismissible via "Continue in background"; the pipeline runs server-side regardless. The user can leave, come back, queue more uploads — the backend doesn't care.

WHAT YOU'RE BUILDING (5 targeted changes):

  1. TAB-BAR RENAME + RE-SCOPE
     The 4-tab structure is unchanged but the second tab now reads "Uploads" (not "Upload"),
     uses a stack/list icon, and routes to /uploads (the Status inbox) — NOT directly to the camera.
     The capture flow is reached via a "+ New capture" button inside the Status inbox (and the
     existing Home hero CTA), both of which present the same bottom sheet.

     - Update the Tabs config: id 'upload', label 'Uploads', icon = three horizontal lines (M5 7h14M5 12h14M5 17h14).
     - Tapping the tab pushes /uploads.
     - Do NOT add a 5th tab. Status is a place; capture is an action; tabs are for places.

  2. NEW ROUTE: /uploads → renders <MobileStatus />
     - Lists uploads in three sections: In flight, Done, Couldn't read.
     - Polls GET /api/uploads on a 2–5 sec cadence whenever any row has status='processing'.
     - Pull-to-refresh always.
     - Prominent "+ New capture" gradient CTA at the top — opens <NewCaptureSheet/>.
     - Tap an in-flight running row  → /uploads/:id (Processing screen, full checklist).
     - Tap an in-flight QUEUED row   → "Cancel ×" affordance (DELETE /api/uploads/:id; only valid
                                       on rows that haven't started yet).
     - Tap a completed row           → /uploads/:id/results.
     - Tap Retry on a failed row     → POST /api/uploads/:id/retry → optimistically insert
                                       new processing row at top.

     QUEUED-ROW VISUAL TREATMENT (when current_stage === 'queued', i.e. queuedBehind > 0):
       - Numbered position badge (1, 2, 3...) on the thumbnail tile.
       - Clock icon (not spinner).
       - Headline "Waiting · N photos ahead".
       - Striped/empty progress bar (no live fill).
       - ETA reads as "total" (full pipeline + queue wait), not "remaining".
       - Action affordance: "Cancel ×" instead of "Open ↗".

  3. <NewCaptureSheet/> — bottom sheet presented from:
     a) Home hero CTA ("Take a photo of the wall calendar")
     b) Status "+ New capture" button
     Both routes call the same sheet. Two options: "📷 Take a photo" (primary), "🖼 Choose from library".
     Slide-up animation, grabber, dim backdrop. Cancel via tap-outside or the inline Cancel link.

  4. PROCESSING SCREEN GAINS:
     - ETA chip in the header subtext: `~{remaining} remaining · we'll let you know when it's done.`
     - Sticky bottom bar with primary "Continue in background" button.
       Tap → router.push('/uploads'). Pipeline is NOT cancelled. SSE stream stays open in the
       background hook (useUploads) so the row updates live in the Status list.

  5. HOME SCREEN GAINS:
     - <InflightBanner /> conditional on `inflightCount > 0`, between greeting and upload CTA.
       Reads `{N} photos processing… · ~{Xs} remaining` + chevron link to /uploads.
     - <UploadsLink /> at the foot of the home scroll. Always visible. Bold (var(--accent))
       when in-flight > 0; muted (var(--fgSoft)) when quiescent.

  6. NEW HOOK: useUploads()
     - Single source of truth backing Home banner + Status list + Processing ETA chip.
     - Returns { uploads: Upload[], inflightCount: number, longestETA: number, refetch, retry(id), cancel(id) }.
     - Internally: SWR or React Query against /api/uploads, with refresh-interval set when inflight > 0.
     - Per-upload SSE subscriptions multiplexed under the hood (one EventSource per active upload).

API CONTRACT (assumed; build the backend to match — see README.md for the full TypeScript shape):

  GET    /api/uploads                  → Upload[]
  GET    /api/uploads/:id/stream       → SSE; each event has { stage, completed_stages, remaining_seconds, ... }
  POST   /api/uploads/:id/retry        → { id: string }    (returns the NEW upload id; original failed row remains)
  DELETE /api/uploads/:id              → 204                (only valid on queued rows; running rows are not user-cancellable in this phase)

ETA MATH (backend responsibility — frontend renders verbatim):
  - Per-stage median duration from completed runs.
  - ETA = Σ(median[stage] for remaining_stages) + queue_wait.
  - queue_wait = Σ(remaining_seconds of pipelines ahead in the queue).
  - Phase 3 ships hard-coded medians; Phase 4+ measures real durations and improves over time.
  - First Phase-4 priority: log per-stage durations from real runs and start updating the medians.
    The first time the user gets "~30 sec" and the actual run takes 4 minutes, trust evaporates.

LOCKED DECISIONS — DO NOT RELITIGATE:
  ✓ Processing is dismissible. (Supersedes v1.)
  ✓ 4 tabs, not 5. Middle tab opens Status, not the camera.
  ✓ Tap-in-flight-row opens FULL Processing screen, not a compact view. Same component for both contexts.
  ✓ Status flips while user is on the list → just refresh in place; no animation.
  ✓ Retry creates a NEW upload row. The original failed row stays as evidence.
  ✓ Home banner appears ONLY when in-flight > 0. The "View all uploads" link is always present.
  ✓ Cancel is allowed only on queued (not-yet-running) rows.
  ✓ No notifications in this phase. Copy "we'll let you know when it's done" is aspirational.

CODING DISCIPLINE:
  - CSS Modules per surface — no inline styles in production code (the design files use inline styles
    only because they are illustrative React-in-Babel-in-the-browser).
  - Reuse all v1 tokens and primitives. No new colors, fonts, radii.
  - Promote local helpers (Spinner, ThumbTile, SectionRule, NewCaptureSheet pieces) to primitives.tsx
    if you find a second consumer. Otherwise keep them co-located.
  - Make `useUploads()` testable in isolation; mock the API in stories.
  - <NewCaptureSheet/> should be a portal-rendered modal sheet, not nested inside whichever screen
    triggered it. One sheet instance lives at the app root, opened/closed by global state or context.

START BY:
  (a) reading the four files listed at the top,
  (b) summarizing the 6 changes back to me in your own words,
  (c) showing me the proposed component/file structure for the patch (existing files touched + new files),
  (d) getting my confirmation before writing code.
```

---

## Notes for the human reviewing this prompt

- **Roll into Phase 3 if possible.** This enhancement is small enough that landing it as part of the same PR as Phase 3 is cleaner than a v2 follow-up. The implementer should make the call.
- **Empty Status state** isn't drawn explicitly in the canvas. When the user has zero uploads, `MobileStatus` should render the same vibe as `EmptyHome` — a quiet "Nothing here yet" + the same "+ New capture" CTA. Implementer's call on exact copy; keep it short.
- **Backend ETA accuracy is the real test.** Hard-coded medians in Phase 3 will be wrong. Plan for real-duration measurement in Phase 4 from day one.
