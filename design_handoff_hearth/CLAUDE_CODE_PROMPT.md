# Claude Code starter prompt — Hearth

Copy the prompt below into Claude Code in an empty repo. The `design_handoff_hearth/` folder (this bundle) should be present at the repo root before you start.

---

```
You are implementing Hearth — a self-hosted app that turns a photo of a hand-written wall calendar into Google Calendar events. The full design spec, tokens, and all 18 reference screens are in ./design_handoff_hearth/.

START BY READING:
  1. design_handoff_hearth/README.md   — full spec, surfaces, tokens, behavior
  2. design_handoff_hearth/design/tokens.js   — design tokens, family palette, SSE stages, mock data
  3. design_handoff_hearth/design/Hearth UI.html   — open this to see all 18 surfaces visually

Then summarize what you understand the product to be (in your own words, ~5 bullets), confirm the stack, and propose a phased build plan before writing code.

CHOSEN STACK (unless you have a strong reason otherwise):
  Frontend:  React 18 + TypeScript + Vite, CSS variables for tokens (lift from tokens.js as :root vars)
  Backend:   Python 3.12 + FastAPI, async, SSE for the processing pipeline
  VLM:       Ollama (qwen2.5-vl:7b) as default; pluggable provider interface for Gemini 2.5 Flash and Claude Haiku 4.5
  Storage:   SQLite, photos on disk (content-addressed)
  Auth:      Google OAuth with offline_access for refresh token
  Deploy:    Docker compose, single-family scale

LOCKED DESIGN DECISIONS (from the design review — do not relitigate):
  - Aesthetic: Ember (warm editorial). Use the Ember tokens from tokens.js.
  - Theme:     Light default, but ship Dark + Sepia as user-toggleable (token swap, no component changes).
  - Provider:  Ollama default. Gemini + Anthropic also wired in Settings UI.
  - Threshold: 85% default, user-adjustable 50–99.
  - Camera:    Landscape default (wall calendars are wide), portrait is a fallback.
  - TV:        Layout A (Editorial) is v1. Layouts B and C ship behind ?layout= flags.
  - Family:    5 members, ink-color-attributed. Ellie = pink (#E17AA1) pending confirmation from the family.

PHASED BUILD ORDER (each phase shippable on its own):
  Phase 1  Project scaffold + token system + design-system primitives (Button, Badge, Shell, Wordmark)
  Phase 2  Onboarding: login + first-run Google OAuth wizard. Auth gating (until setup done, redirect).
  Phase 3  Capture flow: Home → Camera (landscape) → Processing (SSE plumbing, no real VLM yet — fake stages on a timer)
  Phase 4  VLM pipeline backend: preprocessing + grid detection + per-cell loop + ink-color HSV attribution + confidence gate
  Phase 5  Real SSE wiring: backend emits HEARTH_STAGES events, mobile Processing screen consumes them
  Phase 6  Results + Review queue + single-item Review (with cell crop)
  Phase 7  Google Calendar publish (auto-published items only above threshold)
  Phase 8  Desktop calendar (editorial month view) + Admin (Family + Settings)
  Phase 9  TV mode — Layout A (Editorial). LAN-only, no auth.
  Phase 10 States & polish: empty home, token-expired banner, error recovery, theme toggle (Dark, Sepia)

NON-OBVIOUS BEHAVIOR TO PRESERVE (the README has the full list — these are the ones you'll be tempted to get wrong):
  - Confidence is a gate, not a label. Don't show % on auto-published items.
  - Ink color identifies the WRITER, not the subject. "Bryant — dentist" in red ink → Mom's calendar.
  - Processing screen is non-dismissible. Exiting kills the work.
  - TV mode is LAN-only by network boundary, not by auth. No login UI on /tv.

CODING CONVENTIONS:
  - TypeScript strict mode. No `any` without a comment justifying.
  - CSS variables for ALL design tokens. Component styles read from var(--ink), var(--accent), etc.
  - One CSS module or Tailwind preset per screen — no inline styles in production code.
  - Re-author the React components from scratch using the design references; don't copy the design's inline-style JSX verbatim.
  - Server-Sent Events, not WebSockets, for the processing stream — it's one-way and reconnect semantics are simpler.
  - Provider abstraction: VLMProvider interface with `analyzeCell(imageBytes) → {text, confidence}`. Three implementations.

START WITH PHASE 1. Don't write any application code until you've:
  (a) read all three files listed at the top,
  (b) summarized the product back to me,
  (c) shown me the proposed file tree for Phase 1,
  (d) gotten my confirmation.
```

---

## Notes for whoever is driving Claude Code

- **Don't skip the read-then-confirm step.** The design has many small decisions (camera default, confidence gating semantics, ink-color-as-writer-not-subject) that look arbitrary but are intentional. Make Claude prove it understood them.
- **Keep the design files in the repo.** They're cheap, and being able to point Claude back at `design/Hearth UI.html` mid-build for a screen you're working on saves a lot of "what was this supposed to look like" cycles.
- **Phase 4 (the VLM pipeline) is the riskiest.** Time-box it. If qwen2.5-vl:7b doesn't hit acceptable accuracy on real photos of the family's calendar, the threshold + review-queue UX absorbs that — but you'll know early.
- **The Tweaks panel in the design canvas** is a design-time tool. Don't ship it.
