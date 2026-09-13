"""Deterministic, config-driven department routing (P0, Phase 4).

The routing decision is a fixed config table — never an LLM decision. The
classifier scans only persisted patient text (raw answers + structured HPI)
for the configured keywords. Stitch design doc section 4: 9 issues route to
Kayachikitsa, only Sthaulya routes to Panchakarma; a red flag routes to
Emergency and is handled by the safety gate (never reaches this classifier).
"""
from typing import List

from backend.models.schema import Session

KAYACHIKITSA = "Kayachikitsa"
PANCHAKARMA = "Panchakarma"

DEFAULT_DEPARTMENT = KAYACHIKITSA

# (keyword, department) — first match wins. Red flags never reach here.
DEPARTMENT_KEYWORDS: List[List[str]] = [
    ["Sthaulya", PANCHAKARMA],
    ["sthaulya", PANCHAKARMA],
    ["obesity", PANCHAKARMA],
    ["medoroga", PANCHAKARMA],
    ["weight gain", PANCHAKARMA],
    ["detox", PANCHAKARMA],
    ["shodhana", PANCHAKARMA],
]

# Queue token prefix per department (Stitch refs: KY-014, PK-008).
DEPARTMENT_TOKEN_PREFIX = {
    KAYACHIKITSA: "KY",
    PANCHAKARMA: "PK",
}

# Display labels used by patient (P08/P09) and doctor (D01) surfaces.
DEPARTMENT_LABELS = {
    KAYACHIKITSA: "Kayachikitsa OPD",
    PANCHAKARMA: "Panchakarma OPD",
}


def clinical_text(session: Session) -> str:
    """Flatten all persisted patient text used for routing."""
    parts: List[str] = []
    if session.chief_complaint:
        parts.append(session.chief_complaint)
    hpi = session.history_of_present_illness
    for val in (hpi.onset, hpi.duration, hpi.severity, hpi.character):
        if val:
            parts.append(str(val))
    if hpi.associated_symptoms:
        parts.extend(str(s) for s in hpi.associated_symptoms if s is not None)
    for rec in session.answer_records:
        if rec.answer:
            parts.append(rec.answer)
    for raw in session.raw_answers:
        ans = raw.get("answer")
        if ans:
            parts.append(str(ans))
    return " ".join(parts)


def classify_department(session: Session) -> str:
    """Return the department for a completed, safety-clear session."""
    text = clinical_text(session).lower()
    for keyword, dept in DEPARTMENT_KEYWORDS:
        if keyword.lower() in text:
            return dept
    return DEFAULT_DEPARTMENT