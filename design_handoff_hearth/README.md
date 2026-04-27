# Handoff: Hearth

> **A self-hosted bridge from a wall calendar to Google Calendar.**
> Photo → preprocess → per-cell VLM → ink-color attribution → confidence gate → Google Calendar.

---

## Overview

Hearth is a family-scale, self-hosted app that turns a photo of a hand-written wall calendar into structured events on Google Calendar. The whiteboard stays the source of truth; Hearth is the loudspeaker that broadcasts it to every device in the house (phones, laptops, a wall-mounted TV).

The design covers **18 surfaces across mobile, desktop, and TV** in a single browsable design canvas (`design/Hearth UI.html`).

## About the Design Files

The files in `design/` are **design references created in HTML/React/Babel** — interactive prototypes showing intended look and behavior. They are **not production code to copy directly**.

- The HTML file uses inline JSX compiled via `@babel/standalone` for fast iteration. **Do not ship Babel-in-the-browser.**
- The React components are illustrative — they hard-code mock data, use inline styles, and are organized for the design canvas, not for production architecture.
- Your job is to **recreate these designs in the chosen production stack** (see "Recommended stack" below) using its established patterns. Lift the look, the tokens, the copy, the interaction logic — re-author the implementation.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, copy, and interaction states are all locked in. Reproduce pixel-perfectly within the chosen stack.

The design canvas exposes a **Tweaks panel** (top-right of the canvas) — the user has already locked in the chosen variant:

| Tweak | Locked value | Notes |
|---|---|---|
| Aesthetic | **Ember** | Warm editorial — cream paper, deep ink, terracotta accent. (Two unused alternates — Hearthstone, Whiteboard — remain in `tokens.js` and can be deleted.) |
| Theme | **Light** | Dark + Sepia palettes are defined in `tokens.js` and should ship as user-toggleable themes. |
| Vision provider default | **Ollama (local)** | qwen2.5-vl:7b. Gemini and Anthropic providers are also wired in the Settings UI. |
| Confidence threshold default | **85%** | User-adjustable from 50–99 in Settings. |
| Ellie's ink color | **Pink (#E17AA1)** | Originally both Danielle and Eliana were marked "Red" — split so the VLM can attribute correctly. **Confirm with the family before shipping** or pick a different color. |
| TV layout | **Editorial (TV-A)** is the recommended v1. | Two alternates (Minimal, Info-dense) can ship as `?layout=` variants. |

---

## Recommended stack

The user has not committed to a stack. Suggested:

- **Frontend**: React 18 + TypeScript + Vite. CSS variables for the token system (the design already uses `--paper`, `--ink`, `--accent`, etc.). One CSS module or Tailwind preset per screen — no inline styles.
- **Backend**: Python (FastAPI) or Node — the per-cell VLM pipeline is I/O-bound, async-friendly. Use **Server-Sent Events** for the live processing screen (the spec stages are enumerated in `tokens.js → HEARTH_STAGES`).
- **VLM providers** (pluggable): Ollama (`qwen2.5-vl:7b`, default), Gemini 2.5 Flash, Claude Haiku 4.5. Settings UI already exposes the radio.
- **Storage**: SQLite (single-family scale). Photos on local disk under a content-addressed path.
- **Auth**: Google OAuth (offline access for refresh token). Calendar API write scope.
- **TV mode**: Same React app, route `/tv`, full-screen, LAN-only (no auth — protected by network boundary).

---

## Design tokens

All tokens live in **`design/tokens.js`**. Lift directly.

### Family ink palette (`HEARTH_FAMILY_DEFAULT`)
| ID | Display | Role | Hex | Marker color |
|---|---|---|---|---|
| `bryant` | Bryant | Dad | `#2E5BA8` | Blue |
| `danielle` | Danielle | Mom | `#C0392B` | Red |
| `isabella` | Izzy | Age 3 | `#7B4FB8` | Purple |
| `eliana` | Ellie | Age 0 | `#E17AA1` | Pink ⚠ confirm |
| `family` | Family | Everyone | `#D97A2C` | Orange |

These ink colors are **functional** — the VLM uses them for attribution. Changing them requires retraining the HSV histogram bands.

### Ember aesthetic (the v1 choice)
```js
fontDisplay: '"Fraunces", "Source Serif Pro", Georgia, serif'
fontBody:    '"Inter", -apple-system, system-ui, sans-serif'
fontMono:    '"JetBrains Mono", "SF Mono", ui-monospace, monospace'
radius:      14px
radiusLg:    22px

paper:       #F7F1E8   // page background, light theme
paperDeep:   #EFE6D6   // muted surface
ink:         #1F1B16   // primary text
inkSoft:     #5C5246   // secondary text
rule:        #E2D6BF   // borders, dividers
accent:      #B0431F   // terracotta — primary CTAs, links, brand marks
accentSoft:  #E8D2C4   // accent backgrounds, badge fills
success:     #3F7A4A
warn:        #C97A1B
danger:      #A6342B
```

### Theme variants (`HEARTH_THEMES`)
- **Light** (default): `bg = paper`, `fg = ink`
- **Dark**: `bg = #181513`, `fg = #F4EEE3`, `surface = #22201D`
- **Sepia**: `bg = #E9DBC2`, `fg = #3A2E1F`, `surface = #F1E5CF`

All three are CSS-variable swappable — no component changes needed.

---

## Pipeline stages (`HEARTH_STAGES`)

The processing screen subscribes to an SSE stream and renders each stage as it activates. Order is fixed:

1. `received` — Photo received · Saved to local storage
2. `preprocessing` — Preparing image · Rotating, deskewing, perspective fix
3. `grid_detected` — Reading the calendar grid · Found 5 weeks × 7 days
4. `model_loading` — Loading vision model · First time can take 15–25 sec
5. `cell_progress` — Reading cells · Qwen2.5-VL 7B, ~8 sec / cell *(emits per-cell progress: `{cell: 7, total: 35}`)*
6. `color_matching` — Identifying writers by ink color · HSV histogram → family member
7. `date_normalization` — Resolving dates · Cell coords → ISO date
8. `confidence_gating` — Reviewing confidence · Threshold = 85%
9. `publishing` — Saving to Google Calendar · Auto-published events only
10. `done`

Each event from the SSE stream should carry `{ stage: <key>, message?, progress? }`.

---

## Surfaces

The canvas is organized into seven sections — implement in this order; each phase is shippable on its own.

### ① Onboarding & auth
- **Login** (`DesktopLogin`, 1100×720) — single-screen Google sign-in. Until first-run setup is complete, **all authenticated routes redirect here**.
- **Setup · connect Google** (`SetupGoogle`, 1100×780) — first-run wizard step 2. Asks for the Calendar write scope explicitly, shows what we'll do with it.

### ② Capture flow (mobile, the hot path — ~90% of usage)
- **Home** (`MobileHome`, 390×844) — big "Take a photo" CTA, recent-captures list, last-sync indicator.
- **Camera (landscape)** (`MobileUploadLandscape`, default) — phone rotated; viewfinder is wide because wall calendars are wide. Shutter, gallery, close on the right edge; orientation toggle on the left.
- **Camera (portrait fallback)** (`MobileUpload orientation="portrait"`) — shown only if user explicitly toggles or device orientation lock is on. Hint text suggests rotating.
- **Processing — live SSE** (`MobileProcessing`, 390×844) — checklist of `HEARTH_STAGES` with current item showing a spinner; `cell_progress` shows "X of Y cells" inline. Whole screen is non-dismissible until `done`.
- **Results** (`MobileResults`, 390×844) — three-section list: Auto-published (green check), Needs review (warn dot, count → tap to queue), Skipped (low conf, dismissed).

### ③ Review queue
- **Queue list** (`MobileQueue`, 390×844) — one row per item below threshold. **Decision time per item should be under 5 sec** — this is a design constraint, not a goal. Tap row → review screen.
- **Review one item** (`MobileReview`, 390×844) — top: cropped cell from the original photo (so the user sees what the VLM saw). Editable fields: title, date, time, who. Big "Approve" / "Skip" / "Delete" actions.

### ④ Calendar (desktop)
- **Editorial month view** (`DesktopCalendar`, 1280×800) — Hearth-flavored, not a Google Calendar clone. Color-coded by writer using `HEARTH_FAMILY_DEFAULT[*].hex`. Hover an event → quick-glance card with original cell crop.

### ⑤ Admin
- **Family & ink** (`AdminFamily`, 1280×800) — three-column mapping table: Family member ↔ Ink color ↔ Google Calendar (which calendar to publish their events to).
- **Settings** (`AdminSettings`, 1280×800) — vision provider radio, confidence threshold slider, performance / cost notes per provider.

### ⑥ TV mode (LAN-only, wall-mounted display)
- **A · Editorial** (`TVEditorial`, 1280×720) — **recommended v1.** Today + this week, big editorial type, ambient.
- **B · Minimal poster** (`TVMinimal`, 1280×720) — single big "Today" card.
- **C · Info-dense** (`TVDense`, 1280×720) — full month-at-a-glance.
- **D · Portrait variant** (`TVEditorial portrait`, 540×960) — for phones in a charging dock.

### ⑦ States & edge cases
- **Empty home** (`EmptyHome`, 390×844) — first run, before any captures.
- **Error: Google token expired** (`ErrorBanner`, 1280×500) — banner appears across every authenticated route until reconnected. Source: Google's 90-day inactivity rule on refresh tokens.

---

## Non-obvious behavior to preserve

- **Camera defaults to landscape** — the wall calendar is wide, so the viewfinder is wide. Portrait is a fallback, not a peer.
- **Confidence is a gate, not a label.** Above threshold → publishes silently. Below → queues for review. Don't show the user a confidence percentage on the auto-published path; that's noise.
- **Ink color is functional**, not decorative. A family member is identified by *who wrote it*, not *who it's about*. "Bryant — dentist" written in Mom's red goes on Mom's calendar. Make sure error states explain this if a writer can't be identified.
- **The processing screen is non-dismissible** — exiting kills the background work. The spec is firm on this.
- **TV mode is LAN-only by network boundary**, not by auth. No login UI on `/tv`.
- **Until first-run setup completes, every authenticated route redirects to setup.** Hard requirement.

---

## Files in this bundle

```
design_handoff_hearth/
├── README.md                        ← this file
├── CLAUDE_CODE_PROMPT.md            ← copy-paste prompt to start Claude Code
└── design/
    ├── Hearth UI.html               ← open this in a browser to view all 18 surfaces
    ├── tokens.js                    ← design tokens, family palette, mock data, SSE stages
    ├── primitives.jsx               ← buttons, badges, shells, wordmark
    ├── mobile-screens.jsx           ← phone surfaces
    ├── desktop-screens.jsx          ← login, setup, calendar, admin
    ├── tv-screens.jsx               ← TV layouts A/B/C + portrait
    ├── design-canvas.jsx            ← the canvas wrapper (don't ship)
    ├── tweaks-panel.jsx             ← the design-time tweaks UI (don't ship)
    └── ios-frame.jsx                ← iOS frame chrome (don't ship)
```

To view the design: open `design/Hearth UI.html` in any modern browser. No build step needed — Babel runs in the browser.

---

## Open questions for the team

1. **Ellie's ink color** — confirm pink (#E17AA1) or pick another distinct hue. Whatever is chosen needs an HSV band that doesn't collide with the other four.
2. **Self-hosted deploy target** — Docker compose on a NAS? A Raspberry Pi? This affects model choice (Ollama needs ≥16GB RAM for qwen2.5-vl:7b at reasonable speed).
3. **Photo retention policy** — do we keep originals forever (for re-running with better models later) or purge after N days?
4. **TV authentication** — confirming LAN-only is acceptable, or do we want a PIN gate?
