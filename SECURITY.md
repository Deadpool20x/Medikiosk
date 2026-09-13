# Security Policy — MediKiosk

## 🛡️ Security Overview

MediKiosk is designed with a defense-in-depth architecture to ensure patient privacy, clinical integrity, and system resilience.

---

## 📋 Reporting a Vulnerability

If you discover a security vulnerability or potential credential exposure in MediKiosk, please follow responsible disclosure guidelines.

- **Email**: Contact the repository maintainers directly or report via GitHub Security Advisories.
- **Please DO NOT file public GitHub issues** for sensitive security vulnerabilities.
- Provide a detailed description of the vulnerability, reproduction steps, and potential impact.
- Maintainers will acknowledge receipt within 48 hours and coordinate remediation.

---

## 🔑 Credential & Secret Management

1. **Zero Hardcoded Secrets**: No production or live API keys, tokens, passwords, or certificates are stored in the codebase or version control history.
2. **Environment Variable Isolation**:
   - Secrets are loaded dynamically at runtime from local environment files (`.env`, `frontend/.env.local`).
   - All `.env*` files are strictly excluded via `.gitignore`.
   - `.env.example` provides sanitized placeholder templates only.
3. **Secret Masking & Sanitization**:
   - Provider logs and error messages mask API keys.
   - Tracebacks and exception messages do not leak credential headers or internal tokens.

---

## 🌐 Network & Runtime Boundaries

- **Loopback Prototype Profile**: In the Smart India Hackathon (SIH 2026) prototype demonstration profile, services bind to local loopback interfaces (`127.0.0.1:8000` for FastAPI and `localhost:3000` for Next.js).
- **CORS Configuration**: The FastAPI backend restricts Cross-Origin Resource Sharing (CORS) to the explicit frontend origin (`http://localhost:3000`).
- **Database Boundary**: MediKiosk uses an isolated SQLite database engine with thread safety and transactional locking.

---

## 📁 Input Validation & Upload Hardening

MediKiosk implements strict upload validation to prevent injection, tampering, and denial-of-service:
- **Maximum File Size**: Strict 8MB file size limit enforced before disk writes.
- **MIME & Magic Byte Verification**: Uploaded documents are inspected using both HTTP Content-Type headers and binary magic numbers (JPEG `\xFF\xD8\xFF`, PNG `\x89PNG\r\n\x1a\n`, PDF `%PDF`).
- **Dimension and Integrity Checks**: Image payloads undergo decompression and pixel dimension checks to protect against zip bombs or corrupted/malformed image buffers.
- **State Machine Protection**: Upload endpoints enforce active session validation and block uploads for emergency-flagged sessions.

---

## ⚕️ Clinical Safety Invariants

- **Immutable Emergency Flagging**: When clinical triage detects a life-threatening symptom (e.g. chest pain, respiratory distress), `safety_flagged=true` is locked into the session state.
- **Queue Separation**: Emergency-flagged patients cannot receive a standard OPD queue token and cannot be pushed to standard clinic waiting queues. They are routed exclusively to `P05 Emergency Escalation` and displayed on `D04 Emergency Dashboard`.
