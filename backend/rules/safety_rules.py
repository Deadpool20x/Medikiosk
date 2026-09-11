"""Deterministic P0 safety gate. LLM is never involved in safety decisions.

This is a conservative, explicit keyword screen for a demo intake kiosk.
It is NOT a clinical rules engine and must not be presented as one.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from backend.models.schema import Session

# Conservative, explicit red-flag terms. Mirrors the approved Phase 1 list plus
# phrases the Stitch P05/D04 references use (chest tightness/radiating).
# Any rule that was uncertain was left OUT rather than guessed at.
RED_FLAG_PHRASES: List[str] = [
    "chest pain",
    "chest tightness",
    "difficulty breathing",
    "shortness of breath",
    "severe bleeding",
    "unconscious",
    "loss of consciousness",
    "suicidal",
    "stroke",
    "severe allergic",
    "anaphylaxis",
    "cardiac arrest",
]

@dataclass
class SafetyResult:
    flagged: bool = False
    matched_terms: List[str] = field(default_factory=list)
    source: Optional[str] = None  # "raw_answer" | "structured_state"

def _screen_text(text: str) -> List[str]:
    lower = text.lower()
    return [p for p in RED_FLAG_PHRASES if p in lower]

def structured_state_text(session: Session) -> str:
    """Flatten structured Session state into a single screened string.

    Missing fields contribute nothing. An empty/None field is a normal
    incomplete-data state and is explicitly NOT an emergency.
    """
    parts: List[str] = []
    if session.chief_complaint:
        parts.append(session.chief_complaint)
    hpi = session.history_of_present_illness
    for val in (hpi.onset, hpi.duration, hpi.severity, hpi.character):
        if val:
            parts.append(str(val))
    if hpi.associated_symptoms:
        parts.extend(hpi.associated_symptoms)
    return " ".join(parts)

def evaluate_safety(raw_answer: str, session: Session) -> SafetyResult:
    """Evaluate BOTH raw answer text and structured Session state.

    Deterministic only. The raw text is always screened; the structured state
    is screened too so a red flag picked up earlier and persisted (or entered
    via structured extraction) is still caught. Returns a SafetyResult; the API
    contract surfaces it as ``red_flag``.
    """
    raw_matches = _screen_text(raw_answer or "")
    if raw_matches:
        return SafetyResult(flagged=True, matched_terms=raw_matches, source="raw_answer")

    structured = structured_state_text(session)
    struct_matches = _screen_text(structured)
    if struct_matches:
        return SafetyResult(flagged=True, matched_terms=struct_matches, source="structured_state")

    return SafetyResult(flagged=False)