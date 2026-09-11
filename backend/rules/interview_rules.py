from typing import Optional, Dict, Any, List
from backend.models.schema import Session

REQUIRED_FIELDS_ORDER = [
    "chief_complaint",
    "onset",
    "duration",
    "severity",
    "character",
    "associated_symptoms",
]

QUESTION_BANK: Dict[str, str] = {
    "chief_complaint": "What is the primary reason for your visit today?",
    "onset": "When did these symptoms first begin?",
    "duration": "How long have you been experiencing this, and is it constant or intermittent?",
    "severity": "On a scale of 1 to 10 or in your own words, how severe is the pain or discomfort?",
    "character": "Can you describe what the symptom feels like (e.g., sharp, dull, throbbing, aching)?",
    "associated_symptoms": "Are you experiencing any other symptoms, such as fever, nausea, dizziness, or fatigue?",
}

FIELD_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "chief_complaint": {"complaint": "string"},
    "onset": {"onset": "string|null"},
    "duration": {"duration": "string|null"},
    "severity": {"severity": "string|null"},
    "character": {"character": "string|null"},
    "associated_symptoms": {"associated_symptoms": "string[]"},
}

# Ponytail: deterministic keyword screen for P0 red-flag detection.
# Strictly clinical — missing fields are a workflow state, NOT a red flag.
# Upgrade path: move to rules/interview_rules.py with a proper clinical rules engine.
_RED_FLAG_PHRASES: List[str] = [
    "chest pain",
    "difficulty breathing",
    "severe bleeding",
    "unconscious",
    "suicidal",
    "stroke",
    "severe allergic",
    "anaphylaxis",
    "cardiac arrest",
    "loss of consciousness",
]

def get_field_value(session: Session, field: str) -> Optional[Any]:
    if field == "chief_complaint":
        return session.chief_complaint if session.chief_complaint else None
    
    hpi = session.history_of_present_illness
    if field == "onset":
        return hpi.onset
    elif field == "duration":
        return hpi.duration
    elif field == "severity":
        return hpi.severity
    elif field == "character":
        return hpi.character
    elif field == "associated_symptoms":
        return hpi.associated_symptoms if len(hpi.associated_symptoms) > 0 else None
    return None

def get_next_question(session: Session) -> Optional[str]:
    """Returns next question from question bank or None if interview is complete."""
    for field in REQUIRED_FIELDS_ORDER:
        if get_field_value(session, field) is None:
            return QUESTION_BANK[field]
    return None

def get_current_field(session: Session) -> str:
    return session.interview_step

def get_field_schema(field: str) -> Dict[str, Any]:
    return FIELD_SCHEMAS.get(field, {})

def advance_interview_step(session: Session) -> bool:
    """Advances the interview step. Returns True if interview is complete."""
    for field in REQUIRED_FIELDS_ORDER:
        if get_field_value(session, field) is None:
            session.interview_step = field
            session.interview_complete = False
            return False
    session.interview_step = "complete"
    session.interview_complete = True
    return True

def evaluate_safety(raw_answer: str, session: Session) -> bool:
    """Deterministic red-flag screening on raw patient answer text + session state.

    Returns True if safe (no red flags). Returns False if red flag detected.
    Missing required fields are NOT a red flag — they are a workflow state.
    LLM extraction failure must never bypass this function.
    """
    lower = raw_answer.lower()
    for phrase in _RED_FLAG_PHRASES:
        if phrase in lower:
            return False
    return True
