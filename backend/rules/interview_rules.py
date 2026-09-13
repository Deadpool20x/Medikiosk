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

QUESTION_BANK_I18N: Dict[str, Dict[str, str]] = {
    "chief_complaint": {
        "en": "What is the primary reason for your visit today?",
        "hi": "आज अस्पताल आने का आपका मुख्य कारण क्या है?",
        "gu": "આજે દવાખાને આવવાનું તમારું મુખ્ય કારણ શું છે?",
    },
    "onset": {
        "en": "When did these symptoms first begin?",
        "hi": "यह लक्षण सबसे पहले कब शुरू हुए थे?",
        "gu": "આ લક્ષણો સૌથી પહેલાં ક્યારે શરૂ થયાં હતાં?",
    },
    "duration": {
        "en": "How long have you been experiencing this, and is it constant or intermittent?",
        "hi": "यह परेशानी आपको कितने समय से हो रही है, और क्या यह लगातार बनी रहती है या बीच-बीच में होती है?",
        "gu": "આ તકલીફ તમને કેટલા સમયથી થાય છે, અને શું તે સતત રહે છે કે વચ્ચે-વચ્ચે થાય છે?",
    },
    "severity": {
        "en": "On a scale of 1 to 10 or in your own words, how severe is the pain or discomfort?",
        "hi": "अपने शब्दों में या 1 से 10 के पैमाने पर, यह दर्द या परेशानी कितनी गंभीर है?",
        "gu": "તમારા શબ્દોમાં અથવા 1 થી 10 ના માપદંડ પર, આ દુખાવો કે અસ્વસ્થતા કેટલી ગંભીર છે?",
    },
    "character": {
        "en": "Can you describe what the symptom feels like (e.g., sharp, dull, throbbing, aching)?",
        "hi": "क्या आप बता सकते हैं कि यह कैसा महसूस होता है (जैसे तेज, हल्का, जलन या चुभन जैसा)?",
        "gu": "શું તમે જણાવી શકો કે આ કેવું લાગે છે (જેમ કે તીવ્ર, હળવું, બળતરા કે કળતર જેવું)?",
    },
    "associated_symptoms": {
        "en": "Are you experiencing any other symptoms, such as fever, nausea, dizziness, or fatigue?",
        "hi": "क्या आपको कोई अन्य लक्षण भी हैं, जैसे बुखार, उल्टी का मन, चक्कर या अत्यधिक कमजोरी?",
        "gu": "શું તમને અન્ય કોઈ લક્ષણો જણાય છે, જેમ કે તાવ, ઉબકા, ચક્કર કે અશક્તિ?",
    },
}

QUESTION_BANK: Dict[str, str] = {
    k: v["en"] for k, v in QUESTION_BANK_I18N.items()
}

FIELD_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "chief_complaint": {"complaint": "string"},
    "onset": {"onset": "string|null"},
    "duration": {"duration": "string|null"},
    "severity": {"severity": "string|null"},
    "character": {"character": "string|null"},
    "associated_symptoms": {"associated_symptoms": "string[]"},
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
        return hpi.associated_symptoms if hpi.associated_symptoms else None
    return None

def get_next_question(session: Session) -> Optional[str]:
    """Returns next question honoring session language or None if complete."""
    lang = getattr(session, "language", "en") or "en"
    for field in REQUIRED_FIELDS_ORDER:
        if get_field_value(session, field) is None:
            field_dict = QUESTION_BANK_I18N.get(field, {})
            return field_dict.get(lang, field_dict.get("en", QUESTION_BANK.get(field)))
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
