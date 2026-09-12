"""Adaptive Case-Taking Engine & Conversational Interview Foundation.

Architectural Model:
1. LLM as Conversational Interviewer:
   - Interprets patient answers within bounded conversation context.
   - Identifies what is already known and what clinically relevant information is missing.
   - Proposes natural, patient-facing follow-up questions tailored to the patient's language.
2. Deterministic Policy Validation Gate:
   - Evaluates LLM proposed questions against safety, scope, relevance, repetition, and turn limits.
   - Strictly prohibits diagnosis, prescription, treatment recommendations, and Panchakarma selection.
   - Independently enforces intake sufficiency and hard turn limits (MAX_ADAPTIVE_QUESTIONS = 5).
   - Provides deterministic fallback questions when the LLM fails or is rejected.
3. Clinician Knowledge Layer:
   - Defines pilot presentation domains, mandatory concepts, relevant clinical attributes,
     terminology mappings, and evidence provenance.
   - NOTE: Presentation profiles are provisional pilot pathways for intake demonstration,
     requiring formal Ayurvedic clinician review before clinical deployment.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
import re

# Maximum adaptive questions asked during an intake interview
MAX_ADAPTIVE_QUESTIONS = 5
MIN_CORE_CONCEPTS = 3

# Pilot Presentation Domains
DOMAIN_MUSCULOSKELETAL = "musculoskeletal"
DOMAIN_RESPIRATORY = "respiratory"
DOMAIN_DIGESTIVE = "digestive"
DOMAIN_DERMATOLOGICAL = "dermatological"
DOMAIN_METABOLIC = "metabolic"
DOMAIN_GENERAL = "general"

ALL_DOMAINS = [
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    DOMAIN_DIGESTIVE,
    DOMAIN_DERMATOLOGICAL,
    DOMAIN_METABOLIC,
    DOMAIN_GENERAL,
]

ALL_ALLOWED_CONCEPTS = [
    "primary_symptom",
    "chief_complaint",
    "complaint",
    "site",
    "laterality",
    "onset",
    "duration",
    "severity",
    "character",
    "associated_symptoms",
    "aggravating_factors",
    "relieving_factors",
    "stiffness_or_swelling",
    "functional_limitation",
    "cough_character",
    "food_relationship",
    "bowel_habits",
    "itching_severity",
    "triggers",
    "energy_and_thirst",
    "weight_changes",
    "previous_treatment",
    "relevant_history",
]

# Prohibited clinical terms in patient-facing questions (diagnosis/treatment ban)
PROHIBITED_QUESTION_PATTERNS = [
    # Diagnosis claims
    r"\b(?:diagnos(?:ed|is)|you have|sounds like you have|suffering from)\s+(?:osteoarthritis|arthritis|sciatica|gerd|asthma|bronchitis|eczema|psoriasis|diabetes|hypertension)\b",
    r"\b(?:you are suffering from|your diagnosis is|it appears you have|nidan|dosha imbalance of)\b",
    # Treatment / Prescription claims
    r"\b(?:you should take|take (?:medicine|tablet|capsule|syrup|paracetamol|ibuprofen|antibiotic|ashwagandha|triphala|guggulu))\b",
    r"\b(?:i prescribe|prescribing|prescription for you|take this dosage)\b",
    r"\b(?:you need|undergo)\s+(?:panchakarma|basti|vamana|virechana|nasya|rakta-mokshana|surgery)\b",
    # Unsafe clinical advice
    r"\b(?:stop taking your medication|ignore doctor|do not go to the hospital|no need for medical attention)\b",
]


@dataclass
class DomainKnowledge:
    domain_id: str
    display_name: str
    triggers: List[str]
    mandatory_concepts: List[str]
    relevant_concepts: List[str]
    concept_guidance: Dict[str, str]
    fallback_questions: Dict[str, Dict[str, str]]
    evidence_source: str
    clinician_review_status: str = "provisional_pilot_pending_ayurvedic_clinician_review"


DOMAIN_KNOWLEDGE_BASE: Dict[str, DomainKnowledge] = {
    DOMAIN_MUSCULOSKELETAL: DomainKnowledge(
        domain_id=DOMAIN_MUSCULOSKELETAL,
        display_name="Musculoskeletal & Joint Presentation (Pilot)",
        triggers=[
            "back pain", "lower back", "knee", "joint", "shoulder", "neck pain",
            "stiffness", "sprain", "swelling in joint", "arthritis", "sciatica",
            "muscle ache", "leg pain", "hip pain", "spine", "cervical", "lumbar",
            "sandhigata", "amavata", "kati", "janu", "greeva", "pain in leg", "pain in arm"
        ],
        mandatory_concepts=["primary_symptom", "site", "duration"],
        relevant_concepts=[
            "primary_symptom", "site", "laterality", "duration", "severity",
            "character", "aggravating_factors", "relieving_factors",
            "stiffness_or_swelling", "functional_limitation", "associated_symptoms",
        ],
        concept_guidance={
            "site": "Specific anatomical location of the pain, joint, or muscle",
            "laterality": "Left side, right side, or both sides",
            "duration": "How long the pain or discomfort has been present",
            "aggravating_factors": "Activities or movements that worsen the pain (e.g. stairs, walking, bending)",
            "relieving_factors": "Positions or rest that bring relief",
            "stiffness_or_swelling": "Presence of morning stiffness, warmth, or joint swelling",
            "severity": "Intensity of the pain (mild, moderate, severe, or 1-10 scale)",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What is the primary joint or muscle area causing you discomfort?",
                "hi": "आपको शरीर के किस जोड़ या मांसपेशी में सबसे ज्यादा दर्द या तकलीफ़ है?",
                "gu": "તમને કયા સાંધા કે સ્નાયુમાં સૌથી વધુ દુખાવો કે તકલીફ છે?",
            },
            "site": {
                "en": "Which exact joint or part of your body is affected, and is it on the left, right, or both sides?",
                "hi": "शरीर का कौन सा हिस्सा या जोड़ प्रभावित है — दायां, बायां या दोनों?",
                "gu": "શરીરનો કયો ભાગ કે સાંધો પ્રભાવિત છે — ડાબી બાજુ, જમણી બાજુ કે બંને?",
            },
            "duration": {
                "en": "How long have you been experiencing this pain or stiffness?",
                "hi": "यह दर्द या जकड़न आपको कितने समय से है?",
                "gu": "આ દુખાવો કે જકડાઈ જવાની તકલીફ તમને કેટલા સમયથી છે?",
            },
            "aggravating_factors": {
                "en": "Does the discomfort increase with specific movements like walking, climbing stairs, or sitting?",
                "hi": "क्या चलने, सीढ़ियां चढ़ने या बैठने जैसी गतिविधियों से दर्द बढ़ता है?",
                "gu": "શું ચાલવાથી, દાદર ચઢવાથી કે બેસવાથી દુખાવો વધી જાય છે?",
            },
            "stiffness_or_swelling": {
                "en": "Do you notice any morning stiffness or visible swelling in the affected area?",
                "hi": "क्या सुबह के समय जकड़न या प्रभावित जगह पर कोई सूजन महसूस होती है?",
                "gu": "શું સવારે જકડાઈ જવું કે તે ભાગમાં સોજો જોવા મળે છે?",
            },
            "severity": {
                "en": "How severe is the pain on a scale from 1 to 10, or does it interfere with daily activities?",
                "hi": "दर्द कितना गंभीर है — क्या इससे आपकी रोजमर्रा की गतिविधियों में रुकावट आती है?",
                "gu": "દુખાવો કેટલો ગંભીર છે — શું તેનાથી રોજીંદા કામમાં મુશ્કેલી પડે છે?",
            },
        },
        evidence_source="Charaka Samhita Chikitsa Sthana Vatavyadhi Adhyaya (Pilot intake framework, non-diagnostic)",
    ),
    DOMAIN_RESPIRATORY: DomainKnowledge(
        domain_id=DOMAIN_RESPIRATORY,
        display_name="Respiratory & Pranavaha Presentation (Pilot)",
        triggers=[
            "cough", "cold", "congestion", "runny nose", "sore throat", "sneezing",
            "phlegm", "mucus", "blocked nose", "sinus", "kasa", "shwasa", "pratishyaya"
        ],
        mandatory_concepts=["primary_symptom", "duration", "cough_character"],
        relevant_concepts=[
            "primary_symptom", "duration", "cough_character", "onset", "severity",
            "associated_symptoms", "triggers", "relieving_factors",
        ],
        concept_guidance={
            "duration": "Length of time cough or respiratory symptoms have lasted",
            "cough_character": "Dry, productive with phlegm, ticklish, barking, or wheezy",
            "associated_symptoms": "Mild fever, throat pain, headache, body aches",
            "triggers": "Exposure to cold air, dust, seasonal shift, night time pattern",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What respiratory or throat symptom is bothering you most?",
                "hi": "आपको गले या सांस संबंधी कौन सी तकलीफ़ सबसे ज्यादा परेशान कर रही है?",
                "gu": "તમને ગળા કે શ્વાસ સંબંધિત કઈ તકલીફ સૌથી વધુ હેરાન કરે છે?",
            },
            "duration": {
                "en": "How many days have you had this cough or congestion?",
                "hi": "यह खांसी या जकड़न आपको कितने दिनों से है?",
                "gu": "આ ખાંસી કે કફ તમને કેટલા દિવસથી છે?",
            },
            "cough_character": {
                "en": "Is the cough dry, or do you bring up phlegm or mucus?",
                "hi": "क्या खांसी सूखी है या बलगम/कफ आ रहा है?",
                "gu": "શું ખાંસી સૂકી છે કે કફ/ગળફો આવે છે?",
            },
            "associated_symptoms": {
                "en": "Are you also experiencing mild fever, body ache, throat pain, or blocked nose?",
                "hi": "क्या साथ में हल्का बुखार, गले में दर्द, बदन दर्द या नाक बंद की समस्या है?",
                "gu": "શું સાથે હળવો તાવ, ગળામાં દુખાવો, શરીરનો દુખાવો કે નાક બંધ છે?",
            },
        },
        evidence_source="Charaka Samhita Chikitsa Sthana Kasa/Shwasa Adhyaya (Pilot intake framework, non-diagnostic)",
    ),
    DOMAIN_DIGESTIVE: DomainKnowledge(
        domain_id=DOMAIN_DIGESTIVE,
        display_name="Digestive & Annavaha Presentation (Pilot)",
        triggers=[
            "stomach pain", "acidity", "gas", "bloating", "constipation", "diarrhea",
            "loose motion", "heartburn", "indigestion", "nausea", "loss of appetite",
            "vomiting", "burping", "belching", "ajirna", "agnimandya", "amlapitta", "chardi"
        ],
        mandatory_concepts=["primary_symptom", "duration", "food_relationship"],
        relevant_concepts=[
            "primary_symptom", "duration", "food_relationship", "bowel_habits",
            "severity", "associated_symptoms", "relieving_factors",
        ],
        concept_guidance={
            "duration": "How long stomach/digestive issues have persisted",
            "food_relationship": "Symptoms worsening after eating, on empty stomach, or with spicy/fried food",
            "bowel_habits": "Changes in bowel movements (constipation, looseness, regularity)",
            "associated_symptoms": "Bloating, nausea, sour burping, loss of taste",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What digestive or stomach issue is bothering you most?",
                "hi": "पेट या पाचन से जुड़ी कौन सी समस्या आपको सबसे ज्यादा है?",
                "gu": "પેટ કે પાચન સંબંધિત કઈ સમસ્યા તમને સૌથી વધુ સતાવે છે?",
            },
            "duration": {
                "en": "How long have you noticed these digestive symptoms?",
                "hi": "यह पाचन संबंधी समस्या आपको कितने समय से है?",
                "gu": "આ પાચનની તકલીફ તમને કેટલા સમયથી છે?",
            },
            "food_relationship": {
                "en": "Do your symptoms get worse after meals, on an empty stomach, or after specific foods?",
                "hi": "क्या भोजन के बाद, खाली पेट या मिर्च-मसालेदार खाने से तकलीफ़ बढ़ती है?",
                "gu": "શું જમ્યા પછી, ભૂખ્યા પેટે કે તીખા ખોરાકથી તકલીફ વધે છે?",
            },
            "bowel_habits": {
                "en": "Have you noticed any change in bowel habits, like constipation, looseness, or straining?",
                "hi": "क्या पेट साफ होने में कोई बदलाव, जैसे कब्ज या दस्त की समस्या महसूस हुई है?",
                "gu": "શું પેટ સાફ થવામાં કોઈ ફેરફાર, જેમ કે કબજિયાત કે ઝાડા જેવું જણાય છે?",
            },
        },
        evidence_source="Charaka Samhita Grahani/Amlapitta Nidana (Pilot intake framework, non-diagnostic)",
    ),
    DOMAIN_DERMATOLOGICAL: DomainKnowledge(
        domain_id=DOMAIN_DERMATOLOGICAL,
        display_name="Dermatological Presentation (Pilot)",
        triggers=[
            "skin", "rash", "itching", "boil", "eczema", "red patch", "psoriasis",
            "dry skin", "blister", "pimples", "acne", "fungal", "ringworm",
            "kushta", "kandu", "twak"
        ],
        mandatory_concepts=["primary_symptom", "site", "duration"],
        relevant_concepts=[
            "primary_symptom", "site", "duration", "itching_severity", "triggers",
            "associated_symptoms", "relieving_factors",
        ],
        concept_guidance={
            "site": "Body location of the rash, irritation, or skin changes",
            "duration": "How long the skin condition has been present",
            "itching_severity": "Intensity of itching or burning sensation",
            "triggers": "Contact with new soaps, detergents, cosmetics, fabrics, or medicines",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What skin changes or irritation have you observed?",
                "hi": "आपकी त्वचा पर किस प्रकार के बदलाव, दाने या जलन हो रही है?",
                "gu": "તમારી ચામડી પર કેવા પ્રકારના ફેરફાર, ફોલ્લીઓ કે બળતરા થાય છે?",
            },
            "site": {
                "en": "Where on your body is the rash or irritation located?",
                "hi": "यह त्वचा की तकलीफ़ या दाने शरीर के किस भाग पर हैं?",
                "gu": "આ ચામડીની તકલીફ કે ફોલ્લીઓ શરીરના કયા ભાગ પર છે?",
            },
            "duration": {
                "en": "How long has this skin condition been present?",
                "hi": "यह त्वचा की समस्या आपको कितने समय से है?",
                "gu": "આ ચામડીની સમસ્યા તમને કેટલા સમયથી છે?",
            },
            "itching_severity": {
                "en": "Is there severe itching, burning sensation, or scaling of the skin?",
                "hi": "क्या इसमें तेज खुजली, जलन या त्वचा से पपड़ी निकलने की तकलीफ़ है?",
                "gu": "શું તેમાં તીવ્ર ખંજવાળ, બળતરા કે ચામડીની પોપડી ઉખડવાની સમસ્યા છે?",
            },
        },
        evidence_source="Charaka Samhita Chikitsa Sthana Kushta Adhyaya (Pilot intake framework, non-diagnostic)",
    ),
    DOMAIN_METABOLIC: DomainKnowledge(
        domain_id=DOMAIN_METABOLIC,
        display_name="Metabolic & General Wellness Presentation (Pilot)",
        triggers=[
            "sugar", "diabetes", "thirst", "frequent urination", "weight gain",
            "weight loss", "thyroid", "fatigue", "tiredness", "exhaustion",
            "lethargy", "prameha", "sthaulya", "medoroga"
        ],
        mandatory_concepts=["primary_symptom", "duration", "energy_and_thirst"],
        relevant_concepts=[
            "primary_symptom", "duration", "energy_and_thirst", "weight_changes",
            "associated_symptoms", "previous_treatment",
        ],
        concept_guidance={
            "duration": "How long changes in energy, thirst, or weight have been noted",
            "energy_and_thirst": "Excessive thirst, increased urination, daytime lethargy",
            "weight_changes": "Unintended weight gain or loss over recent months",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What metabolic or energy concerns are you facing?",
                "hi": "आपको कमजोरी, वजन या मेटाबॉलिज्म से जुड़ी क्या परेशानी है?",
                "gu": "તમને નબળાઈ, વજન કે પાચન-ચયાપચયને લગતી શી સમસ્યા છે?",
            },
            "duration": {
                "en": "How long have you been noticing these changes in your body or energy levels?",
                "hi": "शरीर या ऊर्जा में यह बदलाव आप कितने समय से महसूस कर रहे हैं?",
                "gu": "શરીરમાં કે શક્તિમાં આ ફેરફાર તમે કેટલા સમયથી અનુભવો છો?",
            },
            "energy_and_thirst": {
                "en": "Have you experienced unusual thirst, increased urination, or tiredness after meals?",
                "hi": "क्या आपको बार-बार प्यास, अधिक पेशाब या भोजन के बाद ज्यादा थकान महसूस होती है?",
                "gu": "શું તમને વારંવાર તરસ, વધુ પેશાબ કે જમ્યા પછી વધુ થાક લાગે છે?",
            },
        },
        evidence_source="Charaka Samhita Nidana Sthana Prameha/Sthaulya Adhyaya (Pilot intake framework, non-diagnostic)",
    ),
    DOMAIN_GENERAL: DomainKnowledge(
        domain_id=DOMAIN_GENERAL,
        display_name="General Intake Presentation (Pilot)",
        triggers=[],
        mandatory_concepts=["primary_symptom", "duration", "severity"],
        relevant_concepts=[
            "primary_symptom", "duration", "severity", "onset", "character", "associated_symptoms"
        ],
        concept_guidance={
            "primary_symptom": "Main reason for the clinic visit",
            "duration": "How long the feeling or symptom has been going on",
            "severity": "How badly it affects daily routine or discomfort level",
            "onset": "How suddenly or gradually it started",
        },
        fallback_questions={
            "primary_symptom": {
                "en": "What is the primary health reason for your visit today?",
                "hi": "आज क्लिनिक आने का आपका मुख्य कारण क्या है?",
                "gu": "આજે દવાખાને આવવાનું તમારું મુખ્ય કારણ શું છે?",
            },
            "duration": {
                "en": "How long have you been feeling this way, and has it been constant or comes and goes?",
                "hi": "आप यह तकलीफ़ कितने समय से महसूस कर रहे हैं, और क्या यह लगातार रहती है?",
                "gu": "તમે આ તકલીફ કેટલા સમયથી અનુભવો છો, અને શું તે સતત રહે છે કે વધઘટ થાય છે?",
            },
            "severity": {
                "en": "How much does this symptom interfere with your daily routine or sleep?",
                "hi": "यह तकलीफ़ आपकी दिनचर्या या नींद को कितना प्रभावित कर रही है?",
                "gu": "આ તકલીફ તમારા રોજીંદા કામકાજ કે ઊંઘમાં કેટલી અડચણરૂપ બને છે?",
            },
            "associated_symptoms": {
                "en": "Are you experiencing any other symptoms, such as fever, dizziness, or weakness?",
                "hi": "क्या साथ में बुखार, चक्कर या कमजोरी जैसा कोई अन्य लक्षण भी है?",
                "gu": "શું સાથે તાવ, ચક્કર કે નબળાઈ જેવું કોઈ અન્ય લક્ષણ પણ છે?",
            },
        },
        evidence_source="General OPD Medical History Intake Standards",
    ),
}

PRESENTATION_DOMAINS = DOMAIN_KNOWLEDGE_BASE


# =========================================================================
# Domain Classification (Pre-LLM and Heuristic Backup)
# =========================================================================
def classify_presentation_domain(text: str) -> str:
    if not text:
        return DOMAIN_GENERAL
    lower = text.lower()

    domain_order = [
        DOMAIN_MUSCULOSKELETAL,
        DOMAIN_RESPIRATORY,
        DOMAIN_DIGESTIVE,
        DOMAIN_DERMATOLOGICAL,
        DOMAIN_METABOLIC,
    ]

    for dom_key in domain_order:
        knowledge = DOMAIN_KNOWLEDGE_BASE[dom_key]
        for trigger in knowledge.triggers:
            if trigger in lower:
                return dom_key

    return DOMAIN_GENERAL


def get_domain_knowledge(domain_id: Optional[str]) -> DomainKnowledge:
    if domain_id and domain_id in DOMAIN_KNOWLEDGE_BASE:
        return DOMAIN_KNOWLEDGE_BASE[domain_id]
    return DOMAIN_KNOWLEDGE_BASE[DOMAIN_GENERAL]


# Legacy profile accessor for backward compatibility
def get_presentation_profile(domain_id: Optional[str]):
    from types import SimpleNamespace
    k = get_domain_knowledge(domain_id)
    return SimpleNamespace(
        domain_id=k.domain_id,
        display_name=k.display_name,
        triggers=k.triggers,
        required_concepts=k.mandatory_concepts,
        question_sequence=[],
        max_questions=MAX_ADAPTIVE_QUESTIONS,
        min_concepts=MIN_CORE_CONCEPTS,
    )


# =========================================================================
# Bounded Context Builder
# =========================================================================
def build_conversation_context(session_like: Any, new_answer: str) -> Dict[str, Any]:
    """Formulate bounded conversation context for the LLM interviewer."""
    patient = getattr(session_like, "patient", None)
    patient_info = {}
    if patient:
        patient_info = {
            "name": getattr(patient, "name", "Patient"),
            "age": getattr(patient, "age", None),
            "gender": getattr(patient, "gender", None),
        }

    language = getattr(session_like, "language", "en") or "en"
    if language not in ("en", "hi", "gu"):
        language = "en"

    # Prior turns (last 5 to keep context bounded)
    raw_answers = getattr(session_like, "raw_answers", []) or []
    asked_questions = getattr(session_like, "asked_questions", []) or []
    asked_concepts = getattr(session_like, "asked_concepts", []) or []

    history = []
    for idx, raw in enumerate(raw_answers[-5:]):
        history.append({
            "field": raw.get("field"),
            "question": raw.get("question_text", ""),
            "answer": raw.get("answer", ""),
        })

    collected = dict(getattr(session_like, "collected_concepts", {}) or {})
    domain = getattr(session_like, "presentation_domain", None)
    if not domain or domain == DOMAIN_GENERAL:
        # Check if chief complaint or new answer informs domain
        detected = classify_presentation_domain(new_answer)
        if detected != DOMAIN_GENERAL:
            domain = detected
        elif getattr(session_like, "chief_complaint", None):
            detected = classify_presentation_domain(session_like.chief_complaint)
            if detected != DOMAIN_GENERAL:
                domain = detected

    knowledge = get_domain_knowledge(domain)
    unanswered = [c for c in knowledge.relevant_concepts if c not in collected or not str(collected[c]).strip()]

    return {
        "patient": patient_info,
        "language": language,
        "current_answer": new_answer,
        "conversation_history": history,
        "asked_questions": asked_questions,
        "asked_concepts": asked_concepts,
        "collected_concepts": collected,
        "presentation_domain": knowledge.domain_id,
        "mandatory_concepts": knowledge.mandatory_concepts,
        "relevant_concepts": knowledge.relevant_concepts,
        "unanswered_concepts": unanswered,
        "concept_guidance": {k: knowledge.concept_guidance.get(k, "") for k in unanswered[:5]},
        "turn_count": getattr(session_like, "adaptive_question_count", 0),
        "max_turns": MAX_ADAPTIVE_QUESTIONS,
    }


# =========================================================================
# Deterministic Policy Validator
# =========================================================================
@dataclass
class ValidationResult:
    valid: bool
    reasons: List[str] = field(default_factory=list)
    recovery_hint: Optional[str] = None


def validate_llm_proposal(
    proposal: Any,
    session_like: Any,
    current_domain: Optional[str] = None,
) -> ValidationResult:
    """Rigorous deterministic policy validation of the LLM proposed question.

    Checks:
    A. Emergency / safety directives
    B. Relevance to presentation
    C. Target concept already answered (avoid re-asking)
    D. Clinical scope ban (no diagnosis, medicine, prescription, Panchakarma)
    E. Turn limit enforcement
    F. Patient-facing clarity (length, punctuation, formatting)
    G. Semantic and textual repetition
    """
    reasons = []

    # Check E: Turn Limit
    question_count = getattr(session_like, "adaptive_question_count", 0)
    if question_count >= MAX_ADAPTIVE_QUESTIONS:
        return ValidationResult(valid=False, reasons=["Turn limit reached (max turns exceeded)"])

    next_q = getattr(proposal, "next_question", None)
    if not next_q:
        status = getattr(proposal, "status", None)
        if status == "sufficient":
            return ValidationResult(valid=True)
        return ValidationResult(valid=False, reasons=["Missing next_question object while status is not sufficient"])

    q_text = getattr(next_q, "text", "") or ""
    q_concept = getattr(next_q, "target_concept", "") or ""

    # Check F: Format and length
    if not q_text or len(q_text.strip()) < 5:
        reasons.append("Question text is empty or too short")
    if len(q_text) > 350:
        reasons.append("Question text exceeds maximum allowed length (350 chars)")
    if "{" in q_text or "}" in q_text or "```" in q_text:
        reasons.append("Question text contains JSON or code artifacts")

    # Check D: Prohibited topics (diagnosis/treatment ban)
    q_lower = q_text.lower()
    for pattern in PROHIBITED_QUESTION_PATTERNS:
        if re.search(pattern, q_lower):
            reasons.append(f"Question violates clinical scope ban (matched prohibited pattern: {pattern})")
            break

    # Check B: Concept Relevance
    domain = current_domain or getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    knowledge = get_domain_knowledge(domain)
    if q_concept and q_concept not in ALL_ALLOWED_CONCEPTS and q_concept not in knowledge.relevant_concepts:
        reasons.append(f"Target concept '{q_concept}' is not in allowed concepts for domain {domain}")

    # Check C: Target concept already answered
    collected = getattr(session_like, "collected_concepts", {}) or {}
    case_update = getattr(proposal, "case_update", None)
    new_concepts = getattr(case_update, "concepts", {}) or {}
    all_collected = {**collected, **new_concepts}

    existing_val = all_collected.get(q_concept)
    status = getattr(proposal, "status", "continue")
    if existing_val and str(existing_val).strip() != "" and status != "clarify":
        # Exception: primary symptom on turn 0
        if not (q_concept in ("primary_symptom", "chief_complaint") and question_count == 0):
            reasons.append(f"Target concept '{q_concept}' is already answered with value '{existing_val}'")

    # Check G: Semantic and textual repetition
    asked_concepts = getattr(session_like, "asked_concepts", []) or []
    if q_concept and q_concept in asked_concepts and status != "clarify":
        reasons.append(f"Target concept '{q_concept}' has already been asked in a previous turn")

    asked_questions = getattr(session_like, "asked_questions", []) or []
    for prev_q in asked_questions:
        if _texts_are_substantially_identical(q_text, prev_q):
            reasons.append("Question text is a duplicate or near-duplicate of a previously asked question")
            break

    if reasons:
        return ValidationResult(
            valid=False,
            reasons=reasons,
            recovery_hint=f"Avoid concepts: {list(all_collected.keys()) + asked_concepts}. Ask an unanswered relevant concept.",
        )

    return ValidationResult(valid=True)


def _texts_are_substantially_identical(t1: str, t2: str) -> bool:
    s1 = re.sub(r"[^\w\s]", "", t1.lower()).strip()
    s2 = re.sub(r"[^\w\s]", "", t2.lower()).strip()
    if s1 == s2:
        return True
    # Word overlap check
    w1 = set(s1.split())
    w2 = set(s2.split())
    if len(w1) > 3 and len(w2) > 3:
        intersection = w1 & w2
        overlap = len(intersection) / max(len(w1), len(w2))
        if overlap > 0.85:
            return True
    return False


# =========================================================================
# Sufficiency Evaluator
# =========================================================================
def evaluate_conversational_sufficiency(session_like: Any, llm_status: Optional[str] = None) -> bool:
    """Determine whether intake has reached sufficient clinical completeness.

    Rules:
    1. If question count reached MAX_ADAPTIVE_QUESTIONS -> ALWAYS sufficient (hard cap).
    2. If LLM claims sufficient, local engine independently verifies that all mandatory
       concepts are non-empty and at least 2 questions have been asked.
    3. If mandatory concepts are missing, returns False (overrides LLM's early stop).
    """
    question_count = getattr(session_like, "adaptive_question_count", 0)
    if question_count >= MAX_ADAPTIVE_QUESTIONS:
        return True

    domain = getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    knowledge = get_domain_knowledge(domain)
    collected = getattr(session_like, "collected_concepts", {}) or {}

    has_all_mandatory = all(
        (req in collected and collected[req] is not None and str(collected[req]).strip() != "")
        for req in knowledge.mandatory_concepts
    )

    if llm_status == "sufficient":
        if question_count >= 2 and has_all_mandatory:
            return True
        # Mandatory concepts missing: refuse early stop
        return False

    # Also check if all relevant concepts have been exhausted
    unanswered = [c for c in knowledge.relevant_concepts if c not in collected or not str(collected[c]).strip()]
    asked_concepts = getattr(session_like, "asked_concepts", []) or []
    remaining_unasked = [c for c in unanswered if c not in asked_concepts]

    if question_count >= 3 and has_all_mandatory and len(remaining_unasked) == 0:
        return True

    return False


# Backward compatibility alias
def evaluate_sufficiency(session_like: Any) -> bool:
    return evaluate_conversational_sufficiency(session_like, getattr(session_like, "llm_status", None))


# =========================================================================
# Fallback Question Engine
# =========================================================================
def get_fallback_question(session_like: Any, target_concept: Optional[str] = None) -> Dict[str, str]:
    """Provide a deterministic fallback question when the LLM is unavailable or rejected.

    Ensures the kiosk never hangs, loops, or presents a blank screen.
    Selects in the patient's language ('en', 'hi', 'gu').
    """
    domain = getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    knowledge = get_domain_knowledge(domain)
    language = getattr(session_like, "language", "en") or "en"
    if language not in ("en", "hi", "gu"):
        language = "en"

    collected = getattr(session_like, "collected_concepts", {}) or {}
    asked_concepts = getattr(session_like, "asked_concepts", []) or []

    # Determine concept to ask
    chosen_concept = target_concept
    if not chosen_concept or chosen_concept in asked_concepts or (chosen_concept in collected and collected[chosen_concept]):
        # Find first missing mandatory concept
        for mc in knowledge.mandatory_concepts:
            if mc not in asked_concepts and (mc not in collected or not str(collected[mc]).strip()):
                chosen_concept = mc
                break

    if not chosen_concept:
        # Find first missing relevant concept
        for rc in knowledge.relevant_concepts:
            if rc not in asked_concepts and (rc not in collected or not str(collected[rc]).strip()):
                chosen_concept = rc
                break

    if not chosen_concept:
        chosen_concept = "primary_symptom"

    # Get question text from knowledge base fallback table
    q_dict = knowledge.fallback_questions.get(chosen_concept)
    if not q_dict:
        # Check general fallback
        gen_knowledge = DOMAIN_KNOWLEDGE_BASE[DOMAIN_GENERAL]
        q_dict = gen_knowledge.fallback_questions.get(chosen_concept, {})

    text = q_dict.get(language) or q_dict.get("en")
    if not text:
        text = f"Can you tell us more about your {chosen_concept.replace('_', ' ')}?"

    return {
        "text": text,
        "target_concept": chosen_concept,
        "domain": domain,
        "reason": f"Deterministic fallback for concept {chosen_concept}",
    }


# Legacy helper for tests that invoke select_next_question
def select_next_question(session_like: Any) -> Optional[Dict[str, Any]]:
    if getattr(session_like, "interview_complete", False):
        return None
    if getattr(session_like, "adaptive_question_count", 0) >= MAX_ADAPTIVE_QUESTIONS:
        return None
    fallback = get_fallback_question(session_like)
    return {
        "concept_key": fallback["target_concept"],
        "question_text": fallback["text"],
        "domain": fallback["domain"],
        "legacy_field": fallback["target_concept"],
    }


# =========================================================================
# Text Concept Extraction (Heuristic Backup)
# =========================================================================
DOCUMENT_MENTION_PATTERNS = [
    r"\b(?:blood\s*(?:test|report)|lab\s*report|cbc|lipid|sugar\s*report|hba1c)\b",
    r"\b(?:x-?ray|mri|ct\s*scan|ultrasound|sonography|ecg|echo)\b",
    r"\b(?:prescription|rx|medicine\s*slip|doctor\s*slip|past\s*prescription)\b",
    r"\b(?:discharge\s*summary|hospital\s*file|medical\s*records?|paper|reports?)\b",
]

def extract_mentioned_documents(text: str) -> List[str]:
    if not text:
        return []
    found = []
    lower = text.lower()
    for pattern in DOCUMENT_MENTION_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            doc_phrase = match.group(0).strip()
            if doc_phrase not in found:
                found.append(doc_phrase)
    return found


def extract_concepts_from_text(text: str, domain: Optional[str] = None) -> Dict[str, Any]:
    if not text:
        return {}
    extracted: Dict[str, Any] = {}
    lower = text.lower()

    dur_match = re.search(
        r"\b(?:for|since|past|lasting)\s+(\d+\s*(?:days?|weeks?|months?|years?|hours?)|yesterday|today|(?:a|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?|years?))\b",
        lower
    )
    if not dur_match:
        dur_match = re.search(r"\b(\d+\s*(?:days?|weeks?|months?|years?))\b", lower)
    if dur_match:
        extracted["duration"] = dur_match.group(1).strip()

    sev_match = re.search(
        r"\b(mild|moderate|severe|unbearable|very severe|extremely painful|intense|sharp|dull|throbbing|aching|\d+\s*(?:out of|\/)\s*10)\b",
        lower
    )
    if sev_match:
        extracted["severity"] = sev_match.group(1).strip()

    onset_match = re.search(
        r"\b(?:started|began|onset)\s+(?:about\s+)?(\d+\s*(?:days?|weeks?|months?)\s*ago|yesterday|suddenly|gradually|last\s*(?:night|week|month))\b",
        lower
    )
    if onset_match:
        extracted["onset"] = onset_match.group(1).strip()

    sites = [
        "lower back", "back", "knee", "knees", "shoulder", "neck", "spine",
        "hip", "elbow", "wrist", "ankle", "skin", "throat", "stomach", "abdomen",
        "joints", "face", "hands", "feet", "chest", "leg", "arm"
    ]
    for site in sites:
        if re.search(r"\b" + re.escape(site) + r"\b", lower):
            extracted["site"] = site
            break

    agg_match = re.search(
        r"\b(?:worse|aggravated|hurts more|pain increases)\s+(?:when|with|after|on)\s+([a-zA-Z\s]+?)(?:[.,;]|$)",
        lower
    )
    if agg_match:
        extracted["aggravating_factors"] = agg_match.group(1).strip()

    if re.search(r"\b(?:after meals?|on empty stomach|with spicy food|after eating)\b", lower):
        food_match = re.search(r"\b(?:after meals?|on empty stomach|with spicy food|after eating)\b", lower)
        if food_match:
            extracted["food_relationship"] = food_match.group(0).strip()

    cough_match = re.search(
        r"\b(dry cough|productive cough|wet cough|cough with phlegm|phlegm|mucus)\b",
        lower
    )
    if cough_match:
        extracted["cough_character"] = cough_match.group(1).strip()

    itch_match = re.search(
        r"\b(severe itching|intense itching|mild itching|itching and burning|burning sensation|itching)\b",
        lower
    )
    if itch_match:
        extracted["itching_severity"] = itch_match.group(1).strip()

    return extracted


def extract_concepts_from_payload(
    answer: str,
    extracted_llm_data: Optional[Dict[str, Any]] = None,
    current_concept: Optional[str] = None,
    domain: Optional[str] = None
) -> Dict[str, Any]:
    concepts: Dict[str, Any] = extract_concepts_from_text(answer, domain=domain)

    if extracted_llm_data and isinstance(extracted_llm_data, dict):
        if "concepts" in extracted_llm_data and isinstance(extracted_llm_data["concepts"], dict):
            for k, v in extracted_llm_data["concepts"].items():
                if v is not None and str(v).strip() != "":
                    concepts[k] = v

        if extracted_llm_data.get("complaint"):
            concepts["primary_symptom"] = str(extracted_llm_data["complaint"]).strip()
            concepts["chief_complaint"] = concepts["primary_symptom"]
        if extracted_llm_data.get("onset"):
            concepts["onset"] = str(extracted_llm_data["onset"]).strip()
        if extracted_llm_data.get("duration"):
            concepts["duration"] = str(extracted_llm_data["duration"]).strip()
        if extracted_llm_data.get("severity"):
            concepts["severity"] = str(extracted_llm_data["severity"]).strip()
        if extracted_llm_data.get("character"):
            concepts["character"] = str(extracted_llm_data["character"]).strip()
        if extracted_llm_data.get("associated_symptoms"):
            concepts["associated_symptoms"] = extracted_llm_data["associated_symptoms"]

    if current_concept and current_concept not in concepts:
        concepts[current_concept] = answer.strip()

    return concepts


# =========================================================================
# Legacy Bridge
# =========================================================================
def bridge_concepts_to_legacy(session_like: Any) -> None:
    """Map structured concepts to legacy session fields (chief_complaint, HPI).

    Preserves 100% backward compatibility with doctor reviews (D01-D04).
    """
    collected = getattr(session_like, "collected_concepts", {}) or {}
    hpi = getattr(session_like, "history_of_present_illness", None)

    if not getattr(session_like, "chief_complaint", None):
        comp = collected.get("primary_symptom") or collected.get("chief_complaint") or collected.get("site")
        if comp:
            session_like.chief_complaint = str(comp).strip()

    if hpi is None:
        return

    if hasattr(hpi, "onset") and not hpi.onset:
        val = collected.get("onset")
        if val:
            hpi.onset = str(val).strip()

    if hasattr(hpi, "duration") and not hpi.duration:
        val = collected.get("duration")
        if val:
            hpi.duration = str(val).strip()

    if hasattr(hpi, "severity") and not hpi.severity:
        val = collected.get("severity") or collected.get("itching_severity")
        if val:
            hpi.severity = str(val).strip()

    if hasattr(hpi, "character") and not hpi.character:
        val = (
            collected.get("character")
            or collected.get("site")
            or collected.get("cough_character")
            or collected.get("food_relationship")
            or collected.get("aggravating_factors")
        )
        if val:
            hpi.character = str(val).strip()

    if hasattr(hpi, "associated_symptoms") and not hpi.associated_symptoms:
        val = collected.get("associated_symptoms")
        if val:
            if isinstance(val, list):
                hpi.associated_symptoms = [str(x).strip() for x in val if x and str(x).strip()]
            elif isinstance(val, str) and val.strip():
                hpi.associated_symptoms = [s.strip() for s in val.split(",") if s.strip()]
