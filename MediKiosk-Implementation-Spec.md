# MediKiosk — Implementation Specification for AI Coding Tools
**Smart India Hackathon 2026 — Problem Statement 26047 (Patient Case-Taking Software)**
**Audience: AI coding agent (Claude Code, Cursor, or equivalent). This is a build spec, not a discussion document.**

---

# 0. INSTRUCTIONS TO THE AI CODING TOOL — READ FIRST

You are the implementation engineer for MediKiosk. Follow this document exactly.

**Hard rules — do not violate these:**

1. Do not invent requirements not written in this document. If something is ambiguous, stop and flag it instead of guessing.
2. Do not add technology, libraries, or services not listed in Section 3. Specifically do not add: LangGraph, PostgreSQL, Redis, Qdrant, any local LLM/OCR/ASR model running on-device. These were evaluated and explicitly rejected (Section 12) — do not reintroduce them because they are common in similar projects.
3. Do not build any item listed in Section 2.2 (Out of Scope). If asked to "make it more complete," these items stay out.
4. Do not let any LLM call decide clinical workflow, required fields, or red-flag/emergency status. The backend rules engine owns that — see Section 8, LLM Boundaries.
5. Every AI-derived value (from LLM, OCR, or speech) must be stored with its confidence score and provider name. Never silently store an AI-derived value as ground truth. See Section 5, Data Model.
6. Never send real, identifiable patient data to Gemini's free tier. Use synthetic/de-identified data only. See Section 11.
7. If an LLM/OCR/speech response fails schema validation, retry once with the backup provider, then mark the field `needs_review: true` and continue — never block the session and never accept invalid data.
8. Follow the day-by-day build order in Section 13. Do not build Day 4 features before Day 1-3 are working end-to-end.
9. When a decision in this document has a research citation attached, treat it as a constraint, not a suggestion. When a decision has no citation (marked "Engineering convention — no research claim"), it can be adjusted if there's a good technical reason, but state the reason.

---

# 1. PROJECT SUMMARY

MediKiosk is an AI-assisted pre-consultation clinical case-taking tool for SIH Problem Statement 26047. It captures patient history (text, and optionally voice) and digitizes prescription/document images, producing a structured, doctor-editable case record. It is explicitly not an autonomous diagnosis system.

Team: 6 members; solo technical build. Timeline: 1 week to a working demo for the SIH internal round, reusable for the grand finale if selected.

---

# 2. SCOPE

## 2.1 In Scope (build and demo live)

- Patient interview: text input, chief complaint → history of present illness → basic history, using a fixed required-field rule set (Section 9).
- LLM-based structured extraction of patient answers into JSON (Section 8).
- **Deterministic red-flag/emergency escalation engine** — runs on raw patient answer text and structured session state, implemented in `rules/interview_rules.py`, purely rule-based, no LLM involvement (Section 8.1).
- Document upload → OCR extraction of medicine name/strength/dose/frequency → confidence scoring → manual correction step for low-confidence fields.
- Doctor dashboard: view structured case, see per-field confidence/source, edit any field, mark case "confirmed."
- Voice input as a stretch feature only (Day 5, conditional — Section 13).

## 2.2 Out of Scope (do not build; roadmap/vision only)

- Real ABDM integration (HIP/HIU registration, consent manager, certification)
- Full AYUSH Prakriti scoring model
- FHIR export, consent workflow, audit logging as running code
- Multi-device concurrent session support
- Hospital Information System (HIS) integration
- Any local model inference (OCR/ASR/LLM run on-device)

If asked to add any of these mid-build, do not — flag it back to the user instead.

---

# 3. TECH STACK (frozen — do not substitute)

| Layer | Choice | Version/notes |
|---|---|---|
| Frontend | Next.js | 14+, TypeScript, App Router |
| Backend | FastAPI | Python 3.11+ |
| Schema validation | Pydantic v2 | used for every LLM/OCR response before it touches the DB |
| Database | SQLite | single file, accessed only through the backend |
| LLM (primary) | Gemini API | free tier — synthetic/de-identified data only (Section 11) |
| LLM (backup) | Groq API | used on Gemini timeout/failure |
| Vision/OCR (primary) | Gemini Vision | |
| Vision/OCR (backup) | Groq (`llama-4-scout-17b-16e-instruct`) | confirmed to support OCR/vision tasks |
| Speech-to-text (primary, stretch only) | Sarvam Saaras v3 | billed ~₹30/hour; free signup credits (~₹1,000) cover hackathon use — not literally free, don't claim it is |
| Speech-to-text (backup, stretch only) | Groq-hosted Whisper Large v3 | |
| Deployment | Local laptop for demo; optional Vercel deploy of frontend | |

---

# 4. FOLDER STRUCTURE (engineering convention — no research claim)

```
medikiosk/
├── frontend/                  # Next.js + TypeScript
│   ├── app/
│   │   ├── patient/           # patient interview flow
│   │   └── doctor/            # doctor dashboard
│   ├── components/
│   └── lib/api.ts             # typed API client
├── backend/                   # FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── session.py         # patient session endpoints
│   │   └── doctor.py          # doctor dashboard endpoints
│   ├── models/
│   │   └── schema.py          # Pydantic models (Section 5)
│   ├── services/
│   │   ├── llm_provider.py    # Gemini/Groq abstraction
│   │   ├── ocr_provider.py    # Gemini Vision/Groq abstraction
│   │   └── speech_provider.py # Sarvam/Groq-Whisper abstraction (stretch)
│   ├── rules/
│   │   └── interview_rules.py # required-field state machine + safety screening (Section 9)
│   └── db.py                  # SQLite access layer
├── data/
│   └── synthetic_patients.json
└── .env                        # API keys, never committed
```

---

# 5. DATA MODEL (Pydantic backend / TypeScript frontend)

```python
# backend/models/schema.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class AnswerRecord(BaseModel):
    question: str
    answer: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DocumentField(BaseModel):
    type: Literal["prescription", "lab_report", "other"]
    extracted_value: Optional[str]
    confidence: float
    source: Literal["ocr", "voice", "manual"]
    provider: Literal["gemini", "groq", "sarvam"]
    needs_review: bool
    manually_corrected: bool = Field(default=False)

class HistoryOfPresentIllness(BaseModel):
    onset: Optional[str] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    character: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    associated_symptoms: list[str] = Field(default_factory=list)

class Patient(BaseModel):
    name: str
    age: int
    gender: str

class DoctorReview(BaseModel):
    edited: bool = Field(default=False)
    confirmed: bool = Field(default=False)

class Session(BaseModel):
    session_id: str
    patient: Patient
    chief_complaint: Optional[str] = Field(default=None)
    history_of_present_illness: HistoryOfPresentIllness = Field(default_factory=HistoryOfPresentIllness)
    documents: list[DocumentField] = Field(default_factory=list)
    doctor_review: DoctorReview = Field(default_factory=DoctorReview)
    answer_records: list[AnswerRecord] = Field(default_factory=list)
```

```typescript
// frontend/lib/types.ts
export interface AnswerRecord {
  question: string;
  answer: string;
  timestamp: string;
}

export interface DocumentField {
  type: "prescription" | "lab_report" | "other";
  extracted_value: string | null;
  confidence: number;
  source: "ocr" | "voice" | "manual";
  provider: "gemini" | "groq" | "sarvam";
  needs_review: boolean;
  manually_corrected: boolean;
}

export interface Session {
  session_id: string;
  patient: { name: string; age: number; gender: string };
  chief_complaint: string | null;
  history_of_present_illness: {
    onset: string | null;
    duration: string | null;
    character: string | null;
    severity: string | null;
    associated_symptoms: string[];
  };
  documents: DocumentField[];
  doctor_review: { edited: boolean; confirmed: boolean };
  answer_records: AnswerRecord[];
}
```

**Rule (research-backed, R4/Section 12):** never overwrite `extracted_value` from `manual` correction back into the AI-derived field — store the manual correction as its own entry with `source: "manual"`, keep the original AI-derived entry intact for auditability.

**SQLite persistence (Section 5):** `answer_records` is stored as a persistent field in the SQLite `sessions` table (e.g., JSON text or a `answers` table with FK to `sessions.session_id`). Both the save path (`/session/{id}/answer`) and the load path (`/doctor/session/{id}` GET, session resume) must round-trip this field verbatim. Every answer submitted by the patient appends a new `AnswerRecord`; the session is never allowed to lose or overwrite an existing record.

---

# 6. API CONTRACT

| Endpoint | Method | Request body | Response body |
|---|---|---|---|
| `/session/start` | POST | `{ "patient": { "name": str, "age": int, "gender": str }, "language": str, "visit_type": str }` | `{ "session_id": str }` **only** (no patient_code) |
| `/session/{id}/answer` | POST | `{ "answer": str }` | `{ "next_question": str \| null, "session_complete": bool }` |
| `/session/{id}/upload` | POST | multipart image file | `{ "extracted_value": str \| null, "confidence": float, "needs_review": bool }` |
| `/session/{id}/consent` | POST | `{ "consent_given": bool }` | `{ "status": str, "detail": str }` — `200` on repeat valid call, never `403` |
| `/session/{id}/status` | GET | — | `{ "ready_for_review": bool }` |
| `/session/{id}/token` | POST | — | `{ "token": str, "department": str }` **or** `{ "error": str, "reason": str }` — returns a queue token only if the session is **completed and safety‑clear** |
| `/doctor/sessions` | GET | — | `[{ "session_id": str, "patient_name": str, "ready_for_review": bool }]` |
| `/doctor/session/{id}` | GET | — | full `Session` object (Section 5) |
| `/doctor/session/{id}` | PATCH | partial `Session` fields to update | updated `Session` object |

**Token eligibility rule (server‑side enforcement):**
A session may receive a normal queue token **only if**:
* All required interview fields are present (`session_complete == true` from `/answer` endpoint),
* No document field has `needs_review: true` (i.e., OCR confidence ≥ 0.5 or manual correction applied), and
* The deterministic safety screening (Section 8.1) evaluated both the raw patient answer text and the structured session state and returned **no red‑flag** (safety‑clear).

If any of the three conditions fails, the `/session/{id}/token` endpoint must return `403` with an error such as `"incomplete_session"`, `"pending_review"`, or `"safety_flagged"` — **never** issue a token or place the session in the normal doctor queue. Safety‑flagged sessions are routed exclusively to an emergency/red‑flag operational view (out of scope for token issuance).

**Error format (all endpoints):** `{ "error": str, "retryable": bool }` — the frontend must never display raw stack traces to the patient (NFR3, Section 2).

---

# 7. LLM PROMPT TEMPLATES (exact — do not paraphrase when implementing)

## 7.1 Structured extraction from patient answer (field-specific)

The prompt must reference the schema for the **current interview field only** (Section 9.1). The implementation must inject the schema dynamically based on the field being answered:

```
System: You are extracting structured medical intake data. Return ONLY valid JSON
matching this schema: {current_field_schema}.
Do not add fields not in this schema. If a field is not mentioned in the patient's
answer, return null for it — do not guess or infer a value the patient did not state.
Do not include any diagnosis, treatment suggestion, or clinical judgment in your response.

User: "{patient_answer_text}"
```

Where `current_field_schema` is one of:
- `{"complaint": string}` (for `chief_complaint`)
- `{"onset": string|null}` (for `onset`)
- `{"duration": string|null}` (for `duration`)
- `{"character": string|null}` (for `character`)
- `{"severity": string|null}` (for `severity`)
- `{"associated_symptoms": string[]}` (for `associated_symptoms`)

This field-specific approach prevents cross-field contamination (e.g., returning onset data when extracting a severity answer).

## 7.2 OCR / document extraction

```
System: Extract medicine name, strength, dose, and frequency from this prescription
image. Return ONLY valid JSON matching this schema: {"medicine": string|null,
"strength": string|null, "dose": string|null, "frequency": string|null,
"confidence": number}. If you cannot read a field clearly, return null for that
field and lower the confidence score accordingly. Never guess a medicine name you
are not reasonably confident about — a wrong medicine name is worse than a
missing one.

[image attached]
```

## 7.3 Physician-readable summary (generated only from already-structured data, never from raw text)

```
System: Convert this structured clinical data into a short, factual summary for a
physician. Do not add any information not present in the input data. Do not
suggest a diagnosis or treatment. If a field is missing or null, state that it is
not available rather than omitting it silently.

Input: {structured_json}
```

**Why this constraint (research-backed, R2/R6, Section 12):** hybrid systems where the LLM only converts already-validated structured data into prose — rather than generating clinical judgments from raw text — are the safer, evidence-supported pattern.

---

# 8. LLM BOUNDARIES

**Core principle: the LLM interprets language. It does not decide clinical workflow.**

| Allowed | Not allowed |
|---|---|
| Phrase a question naturally | Decide which fields are mandatory (owned by `rules/interview_rules.py`) |
| Interpret free text into structured fields | Decide if a symptom is a red flag (deterministic engine owns this, Section 8.1) |
| Extract text/entities from a document image | Decide OCR confidence is "good enough" (fixed threshold in code decides, not the LLM) |
| Generate a physician-readable summary from structured data | Suggest a diagnosis or treatment (never, under any prompt) |

Enforced by: Pydantic schema validation on every LLM/OCR response (Section 5) — a response that fails validation is retried once, then flagged `needs_review: true`, never accepted as-is.

## 8.1 Deterministic safety screening

Safety screening is **deterministic and operates on two independent inputs**:

1. **Raw patient answer text** — the verbatim string submitted by the patient at `/session/{id}/answer`.
2. **Structured session state** — the current `Session` object, including accumulated `answer_records`, `chief_complaint`, `history_of_present_illness`, `documents`, etc.

**Red-flag detection is P0 product scope** — it must be implemented as a deterministic rules engine **outside the LLM**. The LLM is explicitly forbidden from making red-flag decisions (Section 2.2: deterministic red-flag engine is IN scope, but LLM must not decide clinical workflow). All red-flag logic must reside in `rules/interview_rules.py` and be purely rule-based.

The screening function signature is:
```python
def evaluate_safety(raw_answer: str, session: Session) -> bool:
    """
    Returns True if safety conditions are met (no red flags detected).
    Evaluates BOTH raw patient answer text AND structured session state.
    Must be purely deterministic — no LLM involvement in decision.
    """
```

The screening rules engine (Section 9, `rules/interview_rules.py`) evaluates **both inputs** on every call via this function.

**Critical invariant — LLM extraction failure must never bypass red-flag detection.** If the LLM/OCR response fails schema validation and cannot be parsed, the system must still run the deterministic safety screen against the **raw patient answer text** (not the unparseable structured output). The screening rules operate on the raw text regardless of whether extraction succeeded. No code path exists where an LLM/OCR failure prevents safety screening from executing. The session proceeds with `needs_review: true` and the safety screen result appended to the session state.

**Important clarification on red-flag conditions:** Missing required interview fields **must not** trigger a red-flag emergency classification. Incomplete fields remain a workflow state that prevents token issuance (Section 6) but does not constitute a medical emergency. Red-flag conditions are strictly limited to clinically significant findings such as chest pain, difficulty breathing, severe bleeding, neurological deficits, etc. (to be implemented per Section 2.1).

---

# 9. INTERVIEW RULES (required-field state machine — engineering logic, not LLM-decided)

```python
# backend/rules/interview_rules.py — conceptual structure, implement as actual state machine

REQUIRED_FIELDS_ORDER = [
    "chief_complaint",
    "onset",
    "duration",
    "severity",
    "character",
    "associated_symptoms",
]

def get_next_question(session: Session) -> Optional[str]:
    for field in REQUIRED_FIELDS_ORDER:
        if get_field_value(session, field) is None:
            return QUESTION_BANK[field]
    return None  # all required fields collected — interview complete

def evaluate_safety(raw_answer: str, session: Session) -> bool:
    """
    Returns True if safety conditions are met (no red flags detected).
    Evaluates BOTH raw patient answer text AND structured session state.
    Must be purely deterministic — no LLM involvement in decision.
    """
    # Red-flag conditions (strictly clinical, implemented per Section 2.1):
    # - Chest pain
    # - Difficulty breathing
    # - Severe bleeding
    # - Neurological deficits
    # - Other clinically significant findings
    #
    # IMPORTANT: Missing required interview fields are NOT a red-flag condition.
    # Incomplete fields remain a workflow state that prevents token issuance
    # (Section 6) but does not constitute a medical emergency.
    return True  # Placeholder — implement concrete rules per Section 2.1
```

The question bank (`QUESTION_BANK`) is a fixed dictionary of natural-language question templates per field — not generated freely by the LLM per Section 8.

## 9.1 Field-specific LLM extraction schema

The LLM extraction schema is **field-specific**: the current interview field determines the allowed extraction schema. The prompt must reference the schema for the current field only:

- `chief_complaint` → schema: `{"complaint": string}`
- `onset` → schema: `{"onset": string|null}`
- `duration` → schema: `{"duration": string|null}`
- `character` → schema: `{"character": string|null}`
- `severity` → schema: `{"severity": string|null}`
- `associated_symptoms` → schema: `{"associated_symptoms": string[]}`

The LLM must never return fields not in the schema for the current field. This prevents cross-field contamination (e.g., returning onset data when extracting a severity answer).

---

# 10. ERROR HANDLING / FALLBACK RULES (by module joint)

| Joint | Failure | Fallback |
|---|---|---|
| Frontend ↔ Backend | Backend unreachable | Show "connection issue, your progress is saved" — never a raw error |
| Backend ↔ Gemini | Timeout or invalid JSON | Retry once, then call Groq; if both fail, set `needs_review: true`, continue session |
| Backend ↔ OCR provider | Confidence below 0.5 | Store as `needs_review: true`, prompt patient/doctor for manual correction |
| Backend ↔ Speech provider (stretch) | Low confidence or failure | Frontend shows [Speak Again] / [Type Answer] — never forces repeated voice-only retries |
| Backend ↔ SQLite | Write failure | Fail loudly in backend logs; frontend shows retry prompt, never silent data loss |

---

# 11. PRIVACY RULES

1. **Only synthetic or de-identified data is used with Gemini's free tier.** Confirmed via Google's Gemini API terms: free-tier prompts/files are used to improve Google's products and may be human-reviewed; paid tier excludes this. This is a real, confirmed exposure — not a hypothetical.
2. Raw patient input is never deleted or overwritten when an AI-cleaned version is generated — both are retained (Section 5, `manually_corrected` note).
3. No autonomous diagnosis is ever presented as fact — every AI-derived field is editable and carries a confidence score (Section 5).

---

# 12. RESEARCH LOG — decisions with evidence vs. engineering convention

| # | Decision | Basis | Type |
|---|---|---|---|
| R1 | Hybrid rules+AI architecture, not LLM-controlled interview | Scoping review of 86 studies on AI history-taking/triage found hybrid systems predominant; only 6 studies validated fully autonomous systems clinically | Research-backed |
| R2 | Chatbot-based history-taking is a legitimate approach | 2024 systematic review (15 observational studies, 3 RCTs) on chatbots for medical history-taking | Research-backed |
| R3 | Product claim = reduced documentation burden, not autonomous diagnosis | 2026 Nature Medicine RCT, 2,069 patients, 28.7% reduction in consultation duration from an LLM preassessment chatbot | Research-backed |
| R4 | OCR must never silently trust low-confidence output; raw input preserved | Prescription-digitization research treats handwriting recognition as materially harder than printed text, requiring confidence + correction | Research-backed |
| R5 | No autonomous AYUSH/Prakriti scoring model | Critical review: 64 Prakriti tools since 1987, only 20 validated in any form, 2 meeting most criteria | Research-backed |
| R6 | Gemini free tier restricted to synthetic/de-identified data | Directly checked Google's Gemini API Additional Terms of Service | Research-backed (verified directly, not from a paper) |
| R7 | Groq is a valid OCR/vision and Whisper backup | Checked Groq's own documentation for `llama-4-scout-17b-16e-instruct` and hosted Whisper Large v3 | Verified directly |
| R8 | Sarvam STT is not free (~₹30/hour, ₹1,000 signup credit) | Checked Sarvam's pricing page directly | Verified directly |
| R9 | SQLite sufficient; Postgres not needed this round | Demo confirmed single-laptop, no concurrent multi-device requirement | Engineering convention — no research claim, just matches the stated demo constraint |
| R10 | LangGraph, Redis, Qdrant rejected | No orchestration complexity, no scale/concurrency need, no semantic-search/RAG requirement in scope | Engineering convention — no research claim, these are scope-mismatch rejections, not evidence-based findings |
| R11 | Folder structure, naming conventions (Section 4) | — | Engineering convention only — adjust freely if there's a good technical reason, no citation needed |

---

# 13. DAY-BY-DAY BUILD ORDER

| Day | Deliverable | End-of-day check |
|---|---|---|
| 1 | Repo scaffolding (Section 4), `.env` with placeholder keys, synthetic patient data file, Gemini/Groq provider abstraction working with a test call. Spot-check both on 5 sample prescription images. | Can call Gemini and Groq from the backend and get a valid JSON response |
| 2 | `/session/start` and `/session/{id}/answer` working end to end: patient answers text, gets next question, per Section 9 rules and Section 7.1 prompt. Deterministic safety screen on raw answer + session. | A synthetic patient can complete the full text interview via API calls |
| 3 | Doctor dashboard: `/doctor/sessions`, `/doctor/session/{id}` GET/PATCH, frontend rendering the structured case with per-field confidence/source. `/session/{id}/consent` idempotent. | A completed session is visible and editable in the doctor dashboard |
| 4 | `/session/{id}/upload` working: image in, OCR extraction out, confidence-gated, manual correction UI. | Uploading a real sample prescription produces a stored, correctly-flagged `DocumentField` |
| 5 | (Stretch, conditional) Voice input via Sarvam/Groq-Whisper, with [Speak Again]/[Type Answer] fallback. If quality is unusable after testing, skip and mark this row not done. | Either voice works with fallback, or it's cleanly absent — no half-working voice path |
| 6 | End-to-end pass with 5-10 synthetic patients through the full flow; fix breakage found. | Full flow runs without a manual restart, 5 times in a row |
| 7 | Failure-case testing (Section 14), record demo video, deploy frontend. | All failure cases in Section 14 handled without a crash or raw error shown |

**Do not start Day 4 work before Day 2 and 3 are verifiably working end to end.**

---

# 14. TESTING CHECKLIST (before demo day)

- Empty/blank answer at each interview step
- Out-of-range or nonsense input (e.g., age = -5)
- Session interrupted mid-way, browser refreshed — session resumes, not lost
- Blurry, upside-down, or multi-medicine prescription image
- Gemini timeout/invalid JSON → Groq fallback actually triggers
- OCR confidence below threshold → `needs_review` flag appears in the dashboard
- (If voice built) background noise, non-English/code-mixed speech, silence
- `/session/start` returns only `session_id` — no patient_code
- `/session/{id}/consent` is idempotent — repeat valid calls return 200, never 403
- Deterministic safety screen evaluates raw answer text even when LLM extraction fails
- Safety function accepts both `raw_answer` and `Session` (Section 8.1 signature)
- Incomplete interview fields do not trigger red-flag emergency classification
- Field-specific LLM extraction returns only the schema for the current field
- `/session/{id}/token` returns 403 with proper error reason for incomplete, pending-review, or safety-flagged sessions
- `answer_records` round-trips through SQLite save/load and doctor dashboard GET
- Pydantic defaults use `Field(default_factory=...)` — no mutable defaults
- All endpoints, data model, interview state machine, safety section, tests, and DoD use the same contracts with no contradictions

---

# 15. DEFINITION OF DONE (v1, for this hackathon round)

- [ ] Patient can complete the text interview end to end
- [ ] Structured JSON is produced and schema-validated for every session
- [ ] Doctor dashboard shows every field with confidence/source, and is editable
- [ ] Document upload → OCR → confidence-gated extraction works on real sample images
- [ ] All Section 14 failure cases handled without a crash or raw error shown
- [ ] Nothing from Section 2.2 (out of scope) has been built
- [ ] No real patient data has touched Gemini's free tier at any point
- [ ] `/session/start` contract restored: returns `session_id` only, no patient_code
- [ ] `/session/{id}/consent` idempotent — repeat valid calls return 200, never 403
- [ ] Deterministic safety screen evaluates raw answer text and `Session` object
- [ ] Safety function signature: `evaluate_safety(raw_answer: str, session: Session) -> bool`
- [ ] Incomplete interview fields do NOT trigger red-flag emergency classification
- [ ] LLM extraction is field-specific: schema matches current interview field only
- [ ] `/session/{id}/token` returns 403 with proper error reason for incomplete, pending-review, or safety-flagged sessions
- [ ] `answer_records` round-trips through SQLite save/load and doctor dashboard GET
- [ ] All Pydantic defaults use `Field(default_factory=...)` — no mutable defaults
- [ ] API, data model, interview state machine, safety section, tests, and DoD all use the same contracts with no contradictions