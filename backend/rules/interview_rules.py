from typing import Optional, Dict, Any
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
