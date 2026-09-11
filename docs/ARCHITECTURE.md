# MediKiosk System Architecture & Engineering Specifications

This document outlines the detailed software architecture, state machine boundaries, clinical safety guarantees, database mechanics, and AI provider fallback topology of the MediKiosk platform.

---

## 1. Architectural Philosophy & Core Guarantees

MediKiosk is built on an **authoritative state-machine architecture** where:
1. **The LLM is an assistive natural language interpreter and extractor**, NOT an autonomous decision-maker.
2. **Clinical Safety Gates and Department Allocations are 100% deterministic rules engines** implemented in standard Python code.
3. **Queue Tokens cannot be granted** until all state prerequisites (completed interview, document step resolution, and zero safety alerts) are verified in transactional database storage.
4. **Physicians retain full agency** over all clinical records; every AI-extracted entity can be inspected, edited, or corrected before final confirmation.

```
       +---------------------------------------------------------------+
       |                      PATIENT KIOSK (P01-P09)                  |
       +---------------------------------------------------------------+
                                      |
                           (HTTP / REST Session API)
                                      v
+-----------------------------------------------------------------------------+
|                            FASTAPI BACKEND CORE                             |
|                                                                             |
|  +------------------------+  +---------------------+  +------------------+  |
|  |   Session State Mgr    |  |  Safety Screener    |  | Routing Engine   |  |
|  |  - Step transitions    |  |  - Red-flag keywords|  | - Keyword rules  |  |
|  |  - Invariant checks    |  |  - Instant P0 freeze|  | - Dept prefixes  |  |
|  +------------------------+  +---------------------+  +------------------+  |
|                                                                             |
|  +------------------------+  +---------------------+  +------------------+  |
|  |  LLM Provider Adapter  |  | Vision OCR Pipeline |  | Doctor API Guard |  |
|  |  - Groq -> NIM -> OR   |  | - Gemini -> Groq    |  | - Loopback auth  |  |
|  |  - Pydantic validation |  | - Confidence gate   |  | - Token secret   |  |
|  +------------------------+  +---------------------+  +------------------+  |
+-----------------------------------------------------------------------------+
               |                                               |
        (Transactional)                                 (REST Doctor API)
               v                                               v
+-----------------------------+               +-------------------------------+
|  SQLite Storage Engine      |               |  DOCTOR WORKSPACE (D01-D04)   |
|  - WAL mode (concurrent r/w)|               |  - D01: Department Queues     |
|  - 30s busy timeout locks   |               |  - D02: Case Inspector        |
|  - Performance query indexes|               |  - D03: Summary & Edit Form   |
|  - JSON schema persistence  |               |  - D04: Emergency Escalation  |
+-----------------------------+               +-------------------------------+
```

---

## 2. Session Lifecycle & State Machine

Every intake interaction begins by creating a `Session` record identified by a UUIDv4 string and a human-friendly 6-character alphanumeric `patient_code` (e.g. `ABC-123`).

### 2.1 State Progression Stages

| Screen | Phase | Allowed Actions | Validated Invariants |
| :--- | :--- | :--- | :--- |
| **P01** | Language Selection | Pick Language (`en`, `hi`, `mr`, `gu`) | Preferred language stored in session |
| **P02** | Patient Consent | Consent to triage intake | `patient.consent == True` |
| **P03** | Code Issuance | Display 6-char `patient_code` | Session persisted to SQLite |
| **P04** | Clinical Interview | Answer chief complaint & HPI questions | Evaluates safety on each turn; advances through required fields |
| **P05** | Emergency Escalation | Emergency instructions only; no token | Triggered when `safety_flagged == True`. Excluded from standard queues |
| **P06** | Records Upload / OCR | Upload past prescription or skip | File size <= 8MB, MIME verification, magic byte verification, Pillow decode |
| **P07** | Summary & Review | Verify extracted HPI & medications | `documents_complete == True` marked |
| **P08** | Token Issuance | Generate official OPD Queue Token | Requires completed interview, completed docs, and unflagged safety |
| **P09** | Waiting Room Monitor | View current queue position | Live queue updates |

### 2.2 Doctor Workspace Stages

| Screen | View | Purpose | Data Source |
| :--- | :--- | :--- | :--- |
| **D01** | Department Queue | Live patient queues filtered by department | `GET /doctor/queue?department={dept}` |
| **D02** | Case Overview | Complete patient record inspection | `GET /doctor/session/{id}` |
| **D03** | Clinical Review & Edit | Edit symptoms, correct medications, confirm | `PATCH /doctor/session/{id}` |
| **D04** | Emergency Alert Hub | Real-time red-flag cases requiring immediate diversion | `GET /doctor/emergency` |

---

## 3. Clinical Safety Engine & Red-Flag Gate

The safety screening engine (`backend/rules/safety_rules.py`) executes **synchronously** on every user submission during P04. It evaluates both the raw input string and the accumulated structured session state against an explicit, conservative clinical keyword ontology:

```python
RED_FLAG_PHRASES = [
    "chest pain", "chest tightness", "difficulty breathing",
    "shortness of breath", "severe bleeding", "unconscious",
    "loss of consciousness", "suicidal", "stroke",
    "severe allergic", "anaphylaxis", "cardiac arrest"
]
```

### Safety Rules:
1. **Zero LLM Dependency**: The LLM is never consulted to decide if an emergency exists.
2. **Immediate Lockout**: When a red-flag keyword matches:
   - `session.safety_flagged` is set to `True`.
   - `session.status` transitions to `"emergency"`.
   - The API immediately aborts further interview questions and directs the client to P05.
3. **Queue Token Prohibition**: Any call to `POST /session/{id}/token` for a safety-flagged session returns **HTTP 403 Forbidden**.
4. **Confirmation Prevention**: Doctors cannot mark a flagged case as confirmed (`PATCH /doctor/session/{id}` with `doctor_confirmed=True`) without resolving the safety status first (returns **HTTP 409 Conflict**).

---

## 4. Deterministic Department Routing Engine

Department assignment (`backend/rules/department_rules.py`) maps patients to specialized OPD departments based on verified clinical keywords present in the chief complaint and history of present illness.

```
       [ Intake Completed & Unflagged ]
                      |
        Contains keyword "Sthaulya"?
                 /          \
              YES            NO
              /                \
      [ Panchakarma ]     [ Kayachikitsa (Default) ]
      Prefix: "PK-"       Prefix: "KY-"
      Token: PK-008...    Token: KY-014...
```

- **Kayachikitsa OPD** (Internal Medicine): Default OPD destination for systemic, metabolic, and general complaints.
- **Panchakarma OPD** (Purification & Detox): Routed for specific Panchakarma indications such as obesity (`Sthaulya`).
- **Emergency Department**: Immediate destination for any red-flag symptom (bypasses normal OPD queue).

---

## 5. Vision-Language Prescription OCR Pipeline

Prescription digitization (`backend/services/ocr_provider.py`) allows patients to present previous medical prescriptions at the kiosk:

1. **Upload & Sanity Validation**:
   - File size enforced strictly at `<= 8MB`.
   - Content-Type header must be in `{image/jpeg, image/png, image/webp, image/gif, image/tiff}`.
   - Magic bytes verified against expected MIME header.
   - Pillow (`PIL.Image.open`) verifies image payload integrity without truncation.
2. **Provider Failover Order**:
   - **Primary**: Google Gemini Vision (`gemini-2.5-flash`).
   - **Secondary Fallback**: Groq Vision (`qwen/qwen3.6-27b` / `llama-3.2-11b-vision-preview`).
3. **Strict Schema Parsing**:
   - Output parsed into `MedicineExtraction` with fields: `medicine`, `strength`, `dose`, `frequency`, `confidence`.
   - Extra keys rejected via Pydantic (`extra = "forbid"`).
4. **Confidence Gating**:
   - Fixed application threshold `OCR_CONFIDENCE_THRESHOLD = 0.5`.
   - Low confidence flags the medication for explicit doctor review during D03.

---

## 6. Database Architecture & Concurrency Control

MediKiosk utilizes an optimized SQLite database engine (`backend/db.py`) designed for kiosk hardware:
- **Write-Ahead Logging (WAL)**: `PRAGMA journal_mode = WAL;` enables non-blocking concurrent readers while writing.
- **Busy Timeout**: `PRAGMA busy_timeout = 30000;` ensures queries wait up to 30 seconds for locks rather than failing immediately under heavy load.
- **Query Indexes**: Dedicated indexes on `(status, safety_flagged)`, `(department)`, and `(patient_code)` guarantee sub-millisecond lookups for live doctor queues.
- **Atomic Token Generation**: Queue token increments occur inside an explicit `IMMEDIATE` transaction to prevent race conditions or duplicate token issuance.
