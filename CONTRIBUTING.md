# Contributing to MediKiosk

Thank you for your interest in contributing to MediKiosk. This project adheres to rigorous clinical safety, code quality, and test coverage standards.

---

## 1. Code of Conduct & Safety Directives

- **Clinical Integrity First**: Never introduce probabilistic AI decision-making into safety-critical paths. Red-flag detection, queue token issuance, and department allocation must remain strictly deterministic.
- **Privacy & Security**: Never commit real patient data, medical records, or hardcoded API keys. Always use synthetic test fixtures.
- **Full Physician Agency**: Every AI-generated summary or OCR entity must allow physician oversight and manual override.

---

## 2. Development Workflow & TDD

We follow a strict Test-Driven Development (TDD) workflow:

1. **Create an Issue & Branch**:
   - Format: `feat/feature-name`, `fix/issue-description`, or `docs/doc-update`.
2. **Write Failing Tests (RED)**:
   - Add unit/integration tests in `backend/tests/` before writing implementation code.
3. **Implement Feature / Fix (GREEN)**:
   - Implement minimal, robust code to satisfy the tests.
4. **Verify Invariants**:
   - Run the full test suite: `pytest backend/tests -v`
   - Run the invariant audit: `python -m backend.audit`
   - Run frontend build: `npm --prefix frontend run build`
5. **Format & Lint**:
   - Python: Follow PEP 8 and clean typing.
   - Frontend: Follow Next.js App Router and Tailwind CSS best practices.

---

## 3. Pull Request Guidelines

Before submitting a Pull Request:
- [ ] All 164 backend tests pass without errors.
- [ ] The 9/9 clinical invariant audit passes completely.
- [ ] Frontend builds without TypeScript errors (`npx tsc --noEmit`).
- [ ] No secrets, keys, or temporary files are committed.
- [ ] Documentation is updated if endpoints or environment variables change.
