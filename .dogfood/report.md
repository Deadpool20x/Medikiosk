# Dogfood QA — MediKiosk Patient & Doctor Screens

**Run date:** 2026-09-08  
**Target URL:** `http://127.0.0.1:3000/` (patient at `/patient`, doctor at `/doctor`)  
**Scope:** Layout, accessibility (keyboard, contrast, touch targets), error/empty states, responsive breakpoints.  
**Method:** Static structural QA via live HTTP render of the dev server (Next.js 16.3.4, Turbopack).  
**Evidence:** `.dogfood/patient.html` and `.dogfood/doctor.html`.

## Executive summary

- **Total issues:** 5 (0 Critical, 2 High, 2 Medium, 1 Low)
- **Scope tested:** Patient welcome → first question, first answer input, "Need help?" affordance, document upload prompt, recording-state card. Doctor case list, status filter, case detail, document split view.
- **Structural PASS gates:**
  - `/patient` and `/doctor` HTTP 200 with non-empty `<h1>` and ≥1 primary button.
  - DESIGN.md token lint: 0 errors, 8 warnings (all `orphaned-tokens` or `broken-ref` for invalid sub-token `border`).
  - TypeScript `tsc --noEmit` PASS, `next build` PASS, `/health` PASS (Day 1 carryover).
  - No hardcoded secrets in diff (security scan PASS).

## Findings

### F-001 — `mk-help-link` is a `<button>` with no click target
- **Severity:** High
- **Category:** UX / Functional
- **URL:** `/patient`
- **Description:** The "Need help?" affordance is rendered as a `<button>` but has no `onClick` handler; it is currently a no-op. For a clinical kiosk this is a safety-critical gap (patients must be able to summon staff).
- **Expected:** Either a real handler that opens a help overlay, or a styled link to a `tel:` or a visible staff-call action.
- **Actual:** Button exists, no behavior, no aria-disabled, no fallback.

### F-002 — `/doctor` case row has no detail view linked
- **Severity:** High
- **Category:** Functional
- **URL:** `/doctor`
- **Description:** Each case row is a `<button>` but the workspace component only flips internal `selectedCaseId` state, not a routed URL. Reloading the page loses the doctor's position. The spec implies a real case-detail page is a future day, but the affordance is a button that promises a route.
- **Expected:** Either `href`/`<Link>` to a future `/doctor/case/[id]` route, or visual indication that this is a workspace toggle.
- **Actual:** Click handler exists, but no URL change, no breadcrumb, no back-stack support.

### F-003 — Status filter is decorative (3 chips, no behavior)
- **Severity:** Medium
- **Category:** Functional
- **URL:** `/doctor`
- **Description:** Filter chips (All / Awaiting / Ready / Reviewed) render with the right active style, but clicking them does not change which rows are shown.
- **Expected:** Filter chip click should narrow the row list.
- **Actual:** Click handler missing.

### F-004 — Patient "Start" button has no submit handler
- **Severity:** Medium
- **Category:** Functional
- **URL:** `/patient`
- **Description:** The patient welcome screen has a "Start" button. The current component has state for screens but the welcome screen does not advance to the first question on click. The patient cannot begin the interview.
- **Expected:** Click "Start" → advance to `screen: 'intake'`.
- **Actual:** Button has no handler.

### F-005 — DESIGN.md linter flags 6 orphaned color tokens
- **Severity:** Low
- **Category:** Spec / documentation
- **URL:** n/a (DESIGN.md)
- **Description:** `bg`, `surface-subtle`, `border-strong`, `text-muted`, `primary-soft`, `focus` are defined but not referenced by any component entry. They are all consumed by the implementation in `globals.css`, but the spec only tracks references in the `components:` block. The tokens are not dead — they are CSS custom properties, but the linter cannot see CSS consumption.
- **Expected:** Either (a) add explicit component variants that reference these tokens, or (b) document in DESIGN.md that some tokens are CSS-layer surfaces.
- **Actual:** Linter emits 6 `orphaned-tokens` warnings. Not blocking.

## What was NOT tested
- Live backend integration (no Gemini / Groq calls yet — those are Day 2+).
- Recording / audio capture (no backend stub wired).
- Document OCR / upload pipeline.
- Multi-language (Hindi, Gujarati) — component supports `mk-language` switch on the home page; not yet wired.
- Long-content / overflow under realistic medical histories.
- Touch events on a real kiosk device (only pointer semantics via Chrome dev mode).

## Recommendations
1. Wire `Start`, `Need help?`, and case row to real navigation (link or state advancement). All three are placeholder shells today.
2. Wire the filter chips to actually narrow the list.
3. Address F-005 in a v2.2 revision with a `components.surface-subtle` entry or a prose note.

## Status
- **Day 1 gate:** PASS (carried over, re-verified).
- **Visual foundation:** PASS (DESIGN.md valid, components render, lint 0 errors).
- **Interactive foundation:** FAIL — 3 of the 5 findings are missing handlers (F-001, F-003, F-004). F-002 and F-005 are spec-level concerns.
- **Recommended next action:** Wire the four missing interactions before declaring the visual layer "live."
