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
#
# Spec-sourced escalation phrases (clinical_interview_spec_v1.md §4.5/5.5/6.5,
# packet GI-10..13/MS-11..14/RS-10..14): patient-wordable substrings only.
# Combination presentations (e.g. fever + joint swelling) need clinician
# thresholds and are deliberately NOT encoded here (see questionnaire §2.4).
#
# Hindi/Gujarati entries are plain translations of the SAME gate concepts
# (an HI/GU red-flag utterance must escalate exactly like its EN twin).
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
    # Spec §4.5/§6.5 GI + respiratory bleeding / obstruction flags
    "vomiting blood",
    "vomit blood",
    "blood in vomit",
    "blood in stool",
    "bloody stool",
    "black stool",
    "black tarry stool",
    "black and tarry",
    "tarry stool",
    "blood in sputum",
    "blood in my sputum",
    "bloody sputum",
    "sputum with blood",
    "coughing blood",
    "coughing up blood",
    "cough up blood",
    "yellow eyes",
    "turned yellow",
    "yellow skin",
    "jaundice",
    "cannot swallow",
    "difficulty swallowing",
    "severe abdominal pain",
    "severe stomach pain",
    "choking",
    "blue lips",
    "bluish lips",
    "turned blue",
    "breathless at rest",
    "breathlessness at rest",
    # Spec §5.5 musculoskeletal flags
    "bear weight",
    "hot swollen joint",
    "foot drop",
    "saddle numbness",
    "loss of bladder",
    "loss of bowel",
    "sudden weakness",
    # Hindi twins (Devanagari)
    "सीने में दर्द",
    "छाती में दर्द",
    "सांस लेने में",
    "सांस फूल",
    "खून बह रहा",
    "बेहोश",
    "खून की उल्टी",
    "काला मल",
    "मल में खून",
    "बलगम में खून",
    "खून वाली खांसी",
    "पीली आंखें",
    "पीलिया",
    "निगलने में तकलीफ",
    "पेट में तेज दर्द",
    "दम घुट",
    "नीले होंठ",
    "आराम करते समय सांस फूलना",
    "आत्महत्या",
    "लकवा",
    # Gujarati twins
    "છાતીમાં દુખાવો",
    "શ્વાસ લેવામાં",
    "શ્વાસ ફૂલ",
    "લોહી વહી રહ્યું",
    "બેભાન",
    "લોહીની ઊલટી",
    "કાળો મળ",
    "મળમાં લોહી",
    "ગળફામાં લોહી",
    "લોહીવાળી ખાંસી",
    "પીળી આંખો",
    "કમળો",
    "ગળવામાં તકલીફ",
    "પેટમાં તીવ્ર દુખાવો",
    "ગૂંગળામણ",
    "ભૂરા હોઠ",
    "આરામમાં શ્વાસ ફૂલવો",
    "આત્મહત્યા",
    "લકવો",
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
        parts.extend(str(s) for s in hpi.associated_symptoms if s is not None)
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