# MediKiosk Testing & Quality Assurance Guide

MediKiosk maintains strict test-driven development (TDD) standards and clinical invariant verification. Every build must pass all unit, integration, invariant audit, and browser end-to-end tests.

---

## 1. Test Suite Summary

| Test Category | Suite / Runner | Verified Cases | Purpose |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Integration** | `pytest backend/tests` | **164 passing** | State machine, rules, OCR validation, security headers, database locking |
| **Clinical Invariant Audit** | `python -m backend.audit` | **9 / 9 passing** | State-bypass audit, token integrity, red-flag escalation, department routing |
| **Frontend Type Safety** | `npx tsc --noEmit` | **0 errors** | Strict TypeScript component and API type checking |
| **Frontend Production Build** | `npm run build` | **All routes clean** | Next.js 16 SSR & static page pre-rendering verification |
| **Browser E2E Automation** | Playwright / Node.js | **Patient, Safety, Doctor** | Full browser flows (P01 -> P09, D01 -> D04) |

---

## 2. Running Pytest Suite

The backend test suite covers API routes, session lifecycle transitions, security controls, and provider fallbacks.

```bash
# Run all 164 tests
pytest backend/tests -v

# Run with concise summary
pytest backend/tests -q
```

### Key Test Modules
- `backend/tests/test_session_api.py`: Session creation, interview questions, token issuance rules.
- `backend/tests/test_production_hardening.py`: SQLite WAL mode, database indexes, symptom None-guards, doctor auth headers.
- `backend/tests/test_safety.py`: Deterministic red-flag keyword triggers and lockout enforcement.
- `backend/tests/test_ocr.py`: Prescription image upload limits, magic-byte checking, and schema parsing.
- `backend/tests/test_department.py`: Keyword-based department allocation (Kayachikitsa vs Panchakarma).

---

## 3. Running the Clinical Invariant Audit

The invariant audit (`backend/audit.py`) validates the core clinical integrity rules using an isolated, temporary SQLite database:

```bash
python -m backend.audit
```

Expected output:
```
==================================================
AUDIT RESULTS SUMMARY
==================================================
Normal Patient Flow            PASS
Safety Patient                 PASS
OCR Low Confidence             PASS
OCR Provider Failure           PASS
Interview/LLM Failure          PASS
Refresh/Resume                 PASS
Token Integrity                PASS
Doctor Workflow                PASS
Department Separation          PASS
--------------------------------------------------
TOTAL: 9 passed, 0 failed

All audit scenarios PASSED.
Ready for P0 evaluation.
```

---

## 4. Running Frontend Verification

Verify that the Next.js frontend builds cleanly without TypeScript or bundling warnings:

```bash
cd frontend

# Verify TypeScript types
npx tsc --noEmit

# Verify Next.js production compilation
npm run build
```

---

## 5. Running Browser E2E Tests (Playwright)

MediKiosk provides end-to-end browser automation scripts to test complete patient and doctor journeys:

### Prerequisites:
1. Ensure backend is running on `http://localhost:8000`.
2. Ensure frontend is running on `http://localhost:3000`.

### Scenarios:
```bash
# Test 1: Normal Patient Journey (P01 -> P09)
node scripts/e2e_patient_journey.js

# Test 2: Emergency Red-Flag Escalation (P04 -> P05 & D04)
node scripts/e2e_safety_journey.js

# Test 3: Doctor Consultation Workflow (D01 -> D03)
node scripts/e2e_doctor_journey.js
```
