# MediKiosk — Implementation Blueprint v1 (Revised)

## Status

**Implementation is NOT approved to start as a blind UI rewrite yet.**

The repository is a Day-1 foundation with working scaffolding/tests, but its current frontend and backend do not yet implement the frozen Stitch product. This document defines the controlled bridge from the current repository to the frozen UI and final product workflow.

---

## Source-of-truth hierarchy

1. **MediKiosk Final Project Plan** — product scope and workflow truth.
2. **Approved Stitch `screen.png` files** — final visual reference.
3. **`stitch_medikiosk_FINAL/designs/medikiosk_stitch_design.md`** — visual/product design rules.
4. **Current source code** — implementation starting point, not product truth.
5. **Exported Stitch `code.html`** — reference only; never copy unsupported/stale behavior from it.

Do not invent missing requirements.

---

## Current repository audit

### Working foundation

- Next.js frontend exists.
- FastAPI backend exists.
- SQLite persistence exists.
- Pydantic schemas exist.
- Provider abstraction interfaces exist.
- Patient and doctor entry routes exist.
- Synthetic patient data exists.
- Backend test suite: **12/12 passed**.
- TypeScript typecheck: **passed**.
- Next.js version in package: **16.3.4**.

### Build note

The frontend typecheck passes. A production build could not complete in this Linux environment because the checked-in `node_modules` did not contain the Linux Software Compiler (SWC) binary and the environment could not download it. This is an environment/package-install issue, not evidence that the TypeScript source is invalid.

---

## Blocking gaps before implementation is considered complete

## G1 — Patient UI is a placeholder

Current `frontend/components/patient-flow.tsx` is an 8-step local React state demo.

It does not implement the approved P01–P09 route/state model.

Examples of current mismatch:

- P01/P02/P03/P04/P05/P06/P07/P08/P09 are collapsed into generic local steps.
- Patient identity is not collected through the approved workflow.
- Consent is not implemented.
- Patient Code generation/retrieval is not implemented.
- Structured interview persistence is not implemented.
- Red-flag decision path is not implemented.
- Department classification is not implemented.
- Document upload is placeholder UI only.
- Summary confirmation is not implemented.
- Token creation is hard-coded as `A-032`.

### Required direction

Replace the single local-step demo with a reusable patient flow/state machine driven by backend session state.

---

## G2 — Doctor UI is a placeholder and conflicts with frozen Stitch

Current `frontend/components/doctor-workspace.tsx` contains unsupported/invented UI:

- Dashboard
- Analytics
- Patient Sessions counts
- Review Queue count
- Dr. Patel
- General Physician
- AI confidence percentages
- Mark as Completed
- Request More Info
- invented demo cases
- multi-tab generic AI-summary interface

These are not the approved D01–D04 product screens.

### Required direction

Implement the doctor workspace from the frozen D01–D04 screens:

- D01 Kayachikitsa Queue
- D02 Patient Case
- D03 Review & Edit
- D04 Emergency Safety Dashboard

Panchakarma must reuse the same components with department configuration.

---

## G3 — Backend interview answer endpoint is currently a no-op

`POST /session/{session_id}/answer` currently does not store or extract the submitted answer.

It only calls `get_next_question(session)` against unchanged session state.

### Required direction

Implement:

1. receive answer
2. normalize/validate boundary input
3. send to structured extraction layer
4. validate returned structured data with Pydantic
5. merge validated fields into session
6. preserve raw patient answer
7. run deterministic red-flag rules outside the language model
8. advance deterministic interview state
9. return next question / completion / safety branch

---

## G4 — Red-flag path is missing

The final product requires a safety branch.

Required behavior:

```text
patient answer
    ↓
deterministic safety rules
    ├── flagged → pause intake → P05 → D04
    └── safe    → continue interview
```

A language model (LLM) must not be the final workflow authority for this branch.

The red-flag engine must be conservative and deterministic, and the patient UI must not present a diagnosis.

---

## G5 — Department routing/token flow is missing

The repository does not currently implement the final workflow:

```text
safe case
  ↓
department classification
  ↓
Kayachikitsa / Panchakarma
  ↓
summary confirmation
  ↓
token
  ↓
department queue
```

Panchakarma should be implemented as configuration/department data, not as a separate codebase.

---

## G6 — Document/OCR is placeholder

`backend/services/ocr_provider.py` returns `None`.

`POST /session/{session_id}/upload` returns a placeholder response.

Current schema uses a single `extracted_value` field, while the final document flow needs medicine-level extraction and provenance.

### Required direction

Implement:

```text
upload
 ↓
file validation
 ↓
document record
 ↓
vision/OCR provider
 ↓
structured extraction
 ↓
confidence
 ↓
needs_review
 ↓
manual correction
 ↓
doctor review
```

Preserve the original AI/extracted value and the corrected value.

---

## G7 — Voice is placeholder

Speech providers currently return `None`.

The UI shows a voice button without actual speech processing.

### Required direction

Do not visually claim active recording until the provider is connected.

When implemented:

```text
Speak
 ↓
speech-to-text
 ↓
confidence / quality check
 ↓
editable transcript
 ↓
normal interview path
```

Text must always remain the recovery/input path.

---

## G8 — Current schemas are incomplete for the final workflow

The current `Session` model is missing important workflow state such as:

- language
- consent state
- visit type
- patient code
- department
- queue token
- safety/red-flag state
- interview progress/state
- raw responses
- structured provenance
- source/provider metadata on AI-derived fields
- correction history
- document identifier
- medicine extraction collection

### Required direction

Design the schema from the final workflow before implementing UI dependencies.

Do not silently overload unrelated fields.

---

## G9 — Current database schema is too narrow

The database stores a session as several JSON blobs.

That is acceptable for the Day-1 scaffold, but the final workflow needs reliable state transitions and auditable provenance.

Do not redesign to a complex enterprise database without need.

Prefer a small, testable SQLite model that can persist:

- session state
- patient data
- answers
- structured case
- documents
- medicine extractions
- corrections
- department/token state
- emergency/safety state

---

## G10 — Root `DESIGN.md` conflicts with the final Stitch design language

The current root `DESIGN.md` uses a blue/white token system and some rules that do not exactly match the later frozen Stitch package.

### Required direction

Before major UI work, make one explicit visual source-of-truth decision.

Recommended:

- root `DESIGN.md` = production implementation contract
- `stitch_medikiosk_FINAL/designs/medikiosk_stitch_design.md` = Stitch/product screen contract
- reconcile any token conflict once, before coding
- do not allow the coding agent to choose between conflicting values

---

## G11 — Exported Stitch HTML must not be treated as production requirements

Some exported `code.html` files include older or unsupported content.

Therefore the coding agent must **not blindly copy Stitch HTML into Next.js**.

Use:

- approved screenshot for appearance
- final design markdown for tokens/behavior
- project plan for product scope

---

## G12 — Repository archive/build artifacts should not be treated as source

The uploaded repository includes:

- `frontend/node_modules`
- `frontend/.next`
- `backend/.venv`
- Python cache files
- pytest cache
- `.git`
- Ruflo/Claude runtime state and logs

These are useful locally but should not be used as product implementation source.

For development, keep source, config, tests, and intentional project artifacts only.

---

## G13 — Consent endpoint must be idempotent

Current `POST /session/{id}/consent` returns 403 on repeated calls.

### Required direction

Make the endpoint truly idempotent: repeated valid calls return success and do not error. Store consent state once; subsequent calls read the existing state and return the same successful response.

---

## G14 — Persistent answer records required

Current schema does not persist individual answer records with raw text, structured value, source, provider, confidence, and review flag.

### Required direction

Add persistent `answer_records` across all layers:

- **Pydantic** (`backend/models/schema.py`): `AnswerRecord` model with `Field(default_factory=...)` for mutable defaults
- **TypeScript** (`frontend/lib/types.ts`): `AnswerRecord` interface matching backend
- **SQLite** (`backend/db.py`): `answer_records` table with columns for all provenance fields
- **Save/load logic**: CRUD in `backend/db.py` and usage in `backend/routers/session.py`
- **Tests**: Add tests in `backend/tests/test_db.py` and `backend/tests/test_schemas.py`

---

## G15 — Safety screening must evaluate raw text and never be bypassed

Current architecture only runs safety rules after LLM extraction succeeds. If extraction fails, safety check is skipped.

### Required direction

Change safety architecture:

1. Deterministic safety screening runs **first** on raw patient answer text (before LLM extraction)
2. Safety rules also evaluate structured session state (all prior answers)
3. LLM extraction failure **must never bypass** red-flag detection — raw text path always runs
4. New file: `backend/rules/safety_rules.py` with deterministic rules
5. Flow: `POST /answer` → safety check on raw text → if flagged, immediate emergency branch → else continue to LLM extraction + normal flow

---

## G16 — Backend token/completion API contract missing

No endpoint exists to mark a case complete, generate a token, or enforce that only safe completed cases enter the department queue.

### Required direction

Add backend API contract:

- **`POST /session/{id}/complete`** — marks interview complete, generates queue token, sets department. **Only succeeds if**: session status = `COMPLETED` AND no safety flags exist.
- **`GET /doctor/queue/{department}`** — returns only sessions where `status = COMPLETED` AND `safety_flag = false` AND `department` matches.
- Server-side enforcement: safety-flagged sessions **can never** receive a normal token or appear in department queue.
- Token format: `{DEPT_PREFIX}-{SEQ}` (e.g., `KAY-001`, `PAN-001`)
- Add tests verifying ineligible sessions are rejected.

---

## G17 — Mutable Pydantic defaults must use `Field(default_factory=...)`

Several Pydantic models use mutable defaults (e.g., `list = []`, `dict = {}`) which causes shared-state bugs.

### Required direction

Replace all mutable defaults in `backend/models/schema.py` with `Field(default_factory=list)`, `Field(default_factory=dict)`, etc. Verify with tests that independent instances get independent copies.

---

## Final application route/state map

## Patient

```text
P01 Welcome / Language
  ↓
P02 Consent
  ↓
P03 Patient Code
  ↓
P04 Guided Interview
  ├── voice state
  ├── processing state
  └── red flag → P05
  ↓
P06 Document Upload / OCR
  ├── upload
  ├── processing
  ├── extracted
  └── needs review
  ↓
P07 Summary Review
  ├── view
  └── edit
  ↓
P08 Confirmation / Token
  ↓
P09 Waiting / Completion
```

## Doctor

```text
D01 Queue
  ↓
D02 Patient Case
  ↓
D03 Review & Edit
  ↓
Confirm

Safety branch:
P04 → P05 → D04
```

## Department reuse

```text
DoctorQueue(department)
DoctorCase(department)
DoctorReview(department)

department = "Kayachikitsa"
department = "Panchakarma"
```

---

## Recommended implementation phases

## Phase 1 — foundation reconciliation

- reconcile design tokens
- define shared UI components
- define final session/state schema (including answer_records, consent, patient_code, safety_flag, department, token)
- define deterministic workflow state machine
- replace mutable Pydantic defaults with `Field(default_factory=...)`
- preserve working Day-1 tests

### Gate

Types + focused backend tests pass.

---

## Phase 2 — patient vertical slice

Implement one complete path:

```text
P01 → P02 → P03 → P04
```

with real persistence and idempotent consent.

### Gate

A synthetic patient can start a session, consent (idempotent), receive a patient code, answer interview questions, refresh, and resume without losing state. Answer records persisted with full provenance.

---

## Phase 3 — safety branch

Implement:

```text
P04 → red flag → P05 → D04
```

with deterministic safety rules on raw text first, LLM extraction never bypasses safety.

### Gate

A known synthetic red-flag test case is paused and does not receive a normal department token. Safety check runs even when LLM extraction fails.

---

## Phase 4 — document intelligence

Implement:

```text
P06 upload → extraction → confidence → review
```

### Gate

Blurry/invalid/low-confidence cases fail safely and support manual correction.

---

## Phase 5 — summary/token/queue

Implement:

```text
P07 → P08 → P09
```

plus:

```text
D01 → D02 → D03
```

with `POST /session/{id}/complete` generating token only for safe completed cases, and `GET /doctor/queue` enforcing eligibility.

### Gate

Normal synthetic case reaches the doctor queue and can be reviewed/corrected/confirmed. Flagged case never appears in queue.

---

## Phase 6 — Panchakarma reuse

Use the same doctor components with:

```text
department = "Panchakarma"
```

### Gate

No duplicate doctor UI implementation is introduced.

---

## Phase 7 — voice stretch

Implement only after text flow is stable.

### Gate

Voice failure always falls back to text.

---

## Visual implementation rules

For every screen:

1. Start from the approved Stitch screenshot.
2. Use production design tokens.
3. Reuse shared components.
4. Do not copy raw Stitch HTML.
5. Do not invent missing UI.
6. Preserve patient/doctor density difference.
7. Preserve source/confidence indicators.
8. Preserve accessible states.

Test at:

- 390px
- 768px
- 1024px
- 1440px

---

## Acceptance criteria

## Product

- new patient completes text intake
- consent is explicit and idempotent
- patient code is generated/persisted
- interview state survives refresh
- answer records persisted with full provenance (raw, structured, source, provider, confidence, needs_review)
- safety branch works
- safe case reaches department routing
- summary is reviewable
- token/queue entry is created **only** for safe completed cases
- doctor can review/edit/confirm
- document extraction works or fails safely
- Panchakarma reuses the same doctor UI

## Safety

- no diagnosis by the AI
- no treatment recommendation by the AI
- red flags controlled by deterministic workflow logic
- extracted confidence is never presented as medical certainty
- raw AI/extracted value is preserved when corrected
- safety screening evaluates raw text first; LLM failure never bypasses red-flag detection
- safety-flagged sessions can never receive a normal token or queue entry

## UI

- implementation visually matches frozen Stitch references
- no unsupported navigation/modules
- no fake hospital/system statistics
- no fake integrations
- no provider names in patient-facing error states
- no horizontal overflow at supported widths

---

## Immediate next task

**Do not start editing the whole codebase yet.**

First create the final implementation plan and schema/state contract from this blueprint, then implement the smallest vertical slice:

```text
P01 → P02 → P03 → P04
```

This is the safest way to avoid rewriting the project around assumptions.