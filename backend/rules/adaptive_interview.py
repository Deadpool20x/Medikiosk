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

CORE_CLINICAL_CONCEPTS = [
    "primary_symptom",
    "chief_complaint",
    "complaint",
    "onset",
    "duration",
    "severity",
    "character",
    "associated_symptoms",
    "aggravating_factors",
    "relieving_factors",
]

# Prohibited clinical terms in patient-facing questions (diagnosis/treatment ban)
PROHIBITED_QUESTION_PATTERNS = [
    # Diagnosis claims
    r"\b(?:diagnos(?:ed|is)|you have|sounds like you have|suffering from)\s+(?:(?:\w+)\s+)?(?:osteoarthritis|arthritis|sciatica|gerd|asthma|bronchitis|eczema|psoriasis|diabetes|hypertension)\b",
    r"\b(?:you are suffering from|your diagnosis is|it appears you have|nidan|dosha imbalance of)\b",
    r"\b(?:diagnosed with|have been diagnosed with)\b",
    # Treatment / Prescription claims
    r"\b(?:you should take|take (?:medicine|tablet|capsule|syrup|paracetamol|ibuprofen|antibiotic|ashwagandha|triphala|guggulu))\b",
    r"\b(?:i prescribe|prescribing|prescription for you|take this dosage)\b",
    r"\b(?:you need|undergo)\s+(?:panchakarma|basti|vamana|virechana|nasya|rakta-mokshana|surgery)\b",
    # Unsafe clinical advice
    r"\b(?:stop taking your medication|ignore doctor|do not go to the hospital|no need for medical attention)\b",
]


# =========================================================================
# Concept / Domain Category Compatibility
# =========================================================================
# Core concepts that are still clinically meaningless for a specific domain.
# Prevents e.g. asking a metabolic (weakness/fatigue) patient about pain
# character, site, or laterality.
DOMAIN_INCOMPATIBLE_CONCEPTS: Dict[str, Set[str]] = {
    DOMAIN_METABOLIC: {
        "site", "laterality", "character", "stiffness_or_swelling",
        "functional_limitation", "aggravating_factors", "relieving_factors",
        "cough_character", "itching_severity",
    },
    DOMAIN_DIGESTIVE: {
        "laterality", "stiffness_or_swelling",
        "functional_limitation", "cough_character", "itching_severity",
    },
    DOMAIN_RESPIRATORY: {
        "laterality", "stiffness_or_swelling", "functional_limitation",
        "bowel_habits", "food_relationship", "itching_severity",
    },
    DOMAIN_MUSCULOSKELETAL: {
        "cough_character", "food_relationship", "bowel_habits",
        "itching_severity", "energy_and_thirst",
    },
    DOMAIN_DERMATOLOGICAL: {
        "cough_character", "food_relationship", "bowel_habits",
        "energy_and_thirst",
    },
}


# =========================================================================
# Denied-Concepts (Explicit Negatives)
# =========================================================================
# Canonical symptom labels -> concept keys they deny when explicitly negated.
DENIED_SYMPTOM_CONCEPT_MAP: Dict[str, List[str]] = {
    "fever": ["associated_symptoms"],
    "cough": ["cough_character", "primary_symptom"],
    "chest_pain": ["associated_symptoms", "character", "site"],
    "nausea": ["associated_symptoms"],
    "vomiting": ["associated_symptoms"],
    "stiffness": ["stiffness_or_swelling"],
    "swelling": ["stiffness_or_swelling"],
    "itching": ["itching_severity", "associated_symptoms"],
    "fatigue": ["energy_and_thirst"],
    "weakness": ["energy_and_thirst"],
    "headache": ["associated_symptoms"],
    "dizziness": ["associated_symptoms"],
    "diarrhea": ["bowel_habits"],
    "constipation": ["bowel_habits"],
    "phlegm": ["cough_character"],
}

# Negation regexes per script (supports both prefix negation and Indic suffix negation)
NEGATION_PATTERNS = [
    # English prefix: "no fever", "without fever", "don't have fever"
    (r"\b(?:no|not any|without|never had|don'?t have|don'?t get|doesn'?t have|never get)\s+([a-z][a-z\s]{2,40})\b", "en"),
    # English suffix: "fever is not there", "fever: none"
    (r"\b([a-z][a-z\s]{2,40})\s+(?:is not present|is absent|not present|not there|none)\b", "en"),
    # Hindi prefix: "नहीं बुखार", "ना खांसी"
    (r"(?:नहीं|ना|बिना)\s+([\u0900-\u097F][\u0900-\u097F\s]{1,30})", "hi"),
    # Hindi suffix: "बुखार नहीं है", "खांसी नहीं", "उल्टी या चक्कर नहीं"
    (r"([\u0900-\u097F][\u0900-\u097F\s]{1,30})\s+(?:नहीं|ना)(?:\s+है|\s+होता|\s+आती)?", "hi"),
    # Gujarati prefix: "નથી તાવ", "ના ઉધરસ"
    (r"(?:નથી|ના|વિના)\s+([\u0A80-\u0AFF][\u0A80-\u0AFF\s]{1,30})", "gu"),
    # Gujarati suffix: "તાવ નથી", "ખાંસી નથી", "ઊલટી કે ચક્કર નથી"
    (r"([\u0A80-\u0AFF][\u0A80-\u0AFF\s]{1,30})\s+(?:નથી|ના)(?:\s+થતો|\s+આવતી)?", "gu"),
]

# Symptom vocabulary (language -> list of terms) to resolve negated phrases.
NEGATED_SYMPTOM_TERMS: Dict[str, Dict[str, List[str]]] = {
    "en": {
        "fever": ["fever", "temperature"],
        "cough": ["cough"],
        "chest_pain": ["chest pain", "chest discomfort", "chest hurt"],
        "nausea": ["nausea"],
        "vomiting": ["vomiting", "vomit"],
        "stiffness": ["stiffness", "stiffness in the morning"],
        "swelling": ["swelling", "swollen"],
        "itching": ["itching", "itchiness"],
        "fatigue": ["fatigue", "tiredness"],
        "weakness": ["weakness"],
        "headache": ["headache", "head ache"],
        "dizziness": ["dizziness", "dizzy", "giddiness", "spinning"],
        "diarrhea": ["diarrhea", "loose motion"],
        "constipation": ["constipation", "constipated"],
        "phlegm": ["phlegm", "mucus", "sputum"],
    },
    "hi": {
        "fever": ["बुखार", "ताप"],
        "cough": ["खांसी", "खाँसी"],
        "chest_pain": ["सीने में दर्द", "छाती में दर्द", "छाती दर्द"],
        "nausea": ["जी मिचलाना", "मतली"],
        "vomiting": ["उल्टी"],
        "stiffness": ["जकड़न", "अकड़न"],
        "swelling": ["सूजन"],
        "itching": ["खुजली"],
        "fatigue": ["थकान"],
        "weakness": ["कमजोरी", "कमज़ोरी"],
        "headache": ["सिरदर्द", "सिर दर्द"],
        "dizziness": ["चक्कर"],
        "diarrhea": ["दस्त", "पतले दस्त"],
        "constipation": ["कब्ज", "कब्ज़"],
        "phlegm": ["बलगम", "कफ"],
    },
    "gu": {
        "fever": ["તાવ"],
        "cough": ["ખાંસી", "ઉધરસ"],
        "chest_pain": ["છાતીમાં દુખાવો", "છાતીમાં દર્દ", "છાતી દુખવી"],
        "nausea": ["ઉબકા", "ઊબકા"],
        "vomiting": ["ઊલટી", "ઉલટી"],
        "stiffness": ["જકડાઈ", "જકડન"],
        "swelling": ["સોજો"],
        "itching": ["ખંજવાળ"],
        "fatigue": ["થાક"],
        "weakness": ["નબળાઈ"],
        "headache": ["માથાનો દુખાવો", "માથું દુખવું"],
        "dizziness": ["ચક્કર"],
        "diarrhea": ["ઝાડા", "લૂઝ મોશન"],
        "constipation": ["કબજિયાત"],
        "phlegm": ["કફ", "ગળફો"],
    },
}


# =========================================================================
# Regional-Language Normalization (hi/gu -> canonical language-neutral meaning)
# =========================================================================
# Canonical symptom phrases in vernacular script -> (domain, concept, label).
# These are meaning mappings, NOT machine translation. They let the engine
# classify a regional-language answer and bias the LLM towards the correct
# clinical concept instead of hallucinating one.
VERNACULAR_SYMPTOM_MAP: List[Dict[str, Any]] = [
    {"gu": "પેટમાં બળતરા", "domain": DOMAIN_DIGESTIVE, "concept": "primary_symptom", "label": "burning sensation in the stomach"},
    {"gu": "પેટ", "domain": DOMAIN_DIGESTIVE, "concept": "site", "label": "stomach"},
    {"gu": "કમરમાં દુખાવો", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "lower back pain"},
    {"gu": "કમર", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "lower back"},
    {"gu": "ઘૂંટણ", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "knee"},
    {"gu": "સાંધા", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "joint"},
    {"gu": "દુખાવો", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "primary_symptom", "label": "pain"},
    {"gu": "ખાંસી", "domain": DOMAIN_RESPIRATORY, "concept": "primary_symptom", "label": "cough"},
    {"gu": "ગળું", "domain": DOMAIN_RESPIRATORY, "concept": "site", "label": "throat"},
    {"gu": "નાક", "domain": DOMAIN_RESPIRATORY, "concept": "site", "label": "nose"},
    {"gu": "ખંજવાળ", "domain": DOMAIN_DERMATOLOGICAL, "concept": "primary_symptom", "label": "itching"},
    {"gu": "ત્વચા", "domain": DOMAIN_DERMATOLOGICAL, "concept": "site", "label": "skin"},
    {"gu": "નબળાઈ", "domain": DOMAIN_METABOLIC, "concept": "primary_symptom", "label": "weakness"},
    {"gu": "વજન", "domain": DOMAIN_METABOLIC, "concept": "primary_symptom", "label": "weight change"},
    {"hi": "पेट में जलन", "domain": DOMAIN_DIGESTIVE, "concept": "primary_symptom", "label": "burning sensation in the stomach"},
    {"hi": "पेट", "domain": DOMAIN_DIGESTIVE, "concept": "site", "label": "stomach"},
    {"hi": "कमर", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "lower back"},
    {"hi": "घुटना", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "knee"},
    {"hi": "जोड़", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "site", "label": "joint"},
    {"hi": "दर्द", "domain": DOMAIN_MUSCULOSKELETAL, "concept": "primary_symptom", "label": "pain"},
    {"hi": "खांसी", "domain": DOMAIN_RESPIRATORY, "concept": "primary_symptom", "label": "cough"},
    {"hi": "गला", "domain": DOMAIN_RESPIRATORY, "concept": "site", "label": "throat"},
    {"hi": "खुजली", "domain": DOMAIN_DERMATOLOGICAL, "concept": "primary_symptom", "label": "itching"},
    {"hi": "कमजोरी", "domain": DOMAIN_METABOLIC, "concept": "primary_symptom", "label": "weakness"},
    {"hi": "थकान", "domain": DOMAIN_METABOLIC, "concept": "primary_symptom", "label": "fatigue"},
    {"hi": "प्यास", "domain": DOMAIN_METABOLIC, "concept": "energy_and_thirst", "label": "excessive thirst"},
    {"hi": "वजन", "domain": DOMAIN_METABOLIC, "concept": "primary_symptom", "label": "weight change"},
]

# NOTE: vernacular phrases live in distinct scripts (Devanagari U+0900-097F,
# Gujarati U+0A80-0AFF), so substring matching picks the right language.


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
            "sandhigata", "amavata", "kati", "janu", "greeva", "pain in leg", "pain in arm",
            "દુખાવો", "કમર", "ઘૂંટણ", "સાંધા", "જકડાઈ", "સોજો", "ખભા",
            "दर्द", "कमर", "घुटना", "जोड़", "जकड़न", "सूजन", "कंधे", "पीठ"
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
            "phlegm", "mucus", "blocked nose", "sinus", "kasa", "shwasa", "pratishyaya",
            "ખાંસી", "ઉધરસ", "કફ", "ગળું", "નાક", "શ્વાસ",
            "खांसी", "खाँसी", "जुकाम", "कफ", "बलगम", "गला", "नाक", "सांस"
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
            "vomiting", "burping", "belching", "ajirna", "agnimandya", "amlapitta", "chardi",
            "stomach", "burning in my stomach", "burning sensation in my stomach",
            "irregular bowel", "bowel", "burning in the stomach",
            "પેટ", "બળતરા", "એસિડિટી", "ગેસ", "અપચો", "કબજિયાત", "ઝાડા", "ઊલટી", "ઉબકા",
            "पेट", "जलन", "एसिडिटी", "गैस", "अपच", "कब्ज", "दस्त", "उल्टी", "मतली"
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
            "kushta", "kandu", "twak",
            "ચામડી", "ત્વચા", "ખંજવાળ", "ફોલ્લીઓ", "ધાધર",
            "त्वचा", "चमड़ी", "खुजली", "दाने", "दाद"
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
            "lethargy", "prameha", "sthaulya", "medoroga", "weakness",
            "નબળાઈ", "થાક", "તરસ", "પેશાબ", "વજન",
            "कमजोरी", "थकान", "प्यास", "पेशाब", "वजन"
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
def normalize_regional_language(text: str) -> Dict[str, Any]:
    """Map a vernacular (hi/gu) answer to canonical language-neutral meaning.

    Returns a dict with:
      - "domain": detected presentation domain or None
      - "canonical_concepts": {concept_key: canonical english label}
      - "matched_phrases": raw vernacular phrases that matched

    This is a meaning-normalization keyed on clinical symptoms, NOT a machine
    translation. It exists so a Gujarati/Hindi answer is interpreted with the
    same clinical concept as the equivalent English answer.
    """
    if not text:
        return {"domain": None, "canonical_concepts": {}, "matched_phrases": []}
    domain = None
    canonical: Dict[str, str] = {}
    matched: List[str] = []
    for entry in VERNACULAR_SYMPTOM_MAP:
        phrase_v = entry.get("gu") or entry.get("hi")
        if phrase_v and phrase_v in text:
            matched.append(phrase_v)
            canonical[entry["concept"]] = entry["label"]
            if domain is None or entry["domain"] in (DOMAIN_GENERAL,):
                domain = entry["domain"]
    return {"domain": domain, "canonical_concepts": canonical, "matched_phrases": matched}


def extract_denied_concepts(text: str) -> List[str]:
    """Extract explicitly negated symptoms from an answer.

    Supports English, Hindi, and Gujarati (both prefix and suffix negations).
    e.g.:
      - 'no fever', 'no stiffness', 'without chest pain' -> ['fever', 'stiffness', 'chest_pain']
      - 'fever is not there', 'fever absent' -> ['fever']
      - 'बुखार नहीं है', 'उल्टी या चक्कर नहीं' -> ['fever', 'vomiting', 'dizziness']
      - 'તાવ નથી', 'ઊલટી કે ચક્કર નથી' -> ['fever', 'vomiting', 'dizziness']
    Returns canonical symptom labels. The patient is asserted NOT to have them.
    """
    if not text:
        return []
    denied: List[str] = []
    lower = text.lower()

    for pattern, lang in NEGATION_PATTERNS:
        # Check script relevance
        if lang == "hi" and not re.search(r"[\u0900-\u097F]", text):
            continue
        if lang == "gu" and not re.search(r"[\u0A80-\u0AFF]", text):
            continue
        target_str = lower if lang == "en" else text
        for m in re.finditer(pattern, target_str):
            phrase = m.group(1).strip().lower()
            terms = NEGATED_SYMPTOM_TERMS.get(lang, {})
            for symptom, synonyms in terms.items():
                if any(syn in phrase for syn in synonyms):
                    if symptom not in denied:
                        denied.append(symptom)

    return denied


def denied_symptom_concept_keys(denied: List[str]) -> Set[str]:
    """Expand a list of denied symptoms into the concept keys they ban."""
    keys: Set[str] = set()
    for symptom in denied:
        keys.update(DENIED_SYMPTOM_CONCEPT_MAP.get(symptom, []))
    return keys


def find_concept_conflicts(
    new_concepts: Dict[str, Any],
    raw_answer: str,
    collected: Dict[str, Any],
    denied: List[str],
) -> List[str]:
    """Detect clinically suspicious concept updates before they are persisted.

    Conflict sources:
    1. Polarity flips: patient explicitly negated symptom (e.g. 'no fever'),
       but new_concepts records it as present.
    2. Extraction fidelity / Anatomical Contradiction:
       - stomach complaint -> jaw pain / knee pain
       - cough complaint -> knee pain
       - knee complaint -> chest pain
    3. Unanchored hallucination: a proposed multi-word concept value that shares
       no semantic token with the patient's answer or known cross-lingual synonyms.

    Returns human-readable conflict reasons.
    """
    conflicts: List[str] = []
    if not new_concepts:
        return conflicts

    lower_answer = raw_answer.lower()

    # 1. Polarity flips
    if denied:
        expanded = denied_symptom_concept_keys(denied)
        for c_key, c_val in new_concepts.items():
            if c_key in expanded:
                conflicts.append(f"Concept '{c_key}' conflicts with an explicitly denied symptom ({denied})")
            # Also check if value explicitly contains a denied symptom name
            for d in denied:
                if d in str(c_val).lower():
                    conflicts.append(f"Concept '{c_key}' value '{c_val}' contains explicitly denied finding '{d}'")

    # 2. Anatomical and Cross-Domain Contradiction Sanity Layer
    # Define incompatible body-system pairs for pilot domains:
    # (answer_indicator_keywords, forbidden_concept_keywords, description)
    SYSTEM_CONTRADICTIONS = [
        # Stomach / digestive vs Jaw / Tooth / Knee
        (["stomach", "abdomen", "belly", "પેટ", "બળતરા", "पेट", "जलन", "acidity", "indigestion"],
         ["jaw", "tooth", "teeth", "knee", "elbow", "ankle", "दांत", "जबड़ा", "દાંત", "જડબું"],
         "Digestive input contradictory with craniofacial/extremity concept"),

        # Cough / respiratory vs Knee / Back
        (["cough", "congestion", "phlegm", "खांसी", "ખાંસી", "cold", "runny nose"],
         ["knee", "ankle", "foot", "lower back", "घुटना", "ઘૂંટણ"],
         "Respiratory input contradictory with lower limb/back concept"),

        # Knee / Musculoskeletal vs Eye / Ear
        (["knee", "back", "joint", "shoulder", "ઘૂંટણ", "કમર", "घुटना", "कमर"],
         ["eye", "ear", "tooth", "rash on abdomen"],
         "Musculoskeletal input contradictory with unrelated sensory/dermatological concept")
    ]

    for answer_keys, forbidden_words, reason in SYSTEM_CONTRADICTIONS:
        has_answer_indicator = any(ak in lower_answer for ak in answer_keys)
        if has_answer_indicator:
            for c_key, c_val in new_concepts.items():
                val_lower = str(c_val).lower()
                for fw in forbidden_words:
                    if fw in val_lower:
                        conflicts.append(f"Concept '{c_key}' has value '{c_val}' which violates clinical meaning: {reason}")
                        break

    # 3. Unanchored hallucination check
    answer_words = set(re.findall(r"[a-z\u0900-\u097F\u0A80-\u0AFF]{3,}", lower_answer))
    if not answer_words:
        return conflicts

    stop = {"the", "and", "for", "with", "have", "has", "had", "was", "were", "been", "can", "you", "your", "not"}
    for c_key, value in new_concepts.items():
        val = str(value).strip().lower()
        if not val or len(val.split()) < 2:
            continue
        val_words = set(re.findall(r"[a-z\u0900-\u097F\u0A80-\u0AFF]{3,}", val)) - stop
        shared = val_words & answer_words
        # Only flag values that are entirely foreign to the patient's words.
        if val_words and len(shared) == 0 and guess_synonym_overlap(value, raw_answer) == 0:
            conflicts.append(f"Concept '{c_key}' value '{value}' is not supported by the patient's answer")

    return conflicts


def guess_synonym_overlap(value: str, raw_answer: str) -> int:
    """Resolve cross-language and clinical synonyms for fidelity checking."""
    synonym_groups = [
        ("stomach", "પેટ"), ("stomach", "पेट"), ("burning", "બળતરા"), ("burning", "जलन"),
        ("back", "કમર"), ("back", "कमर"), ("knee", "ઘૂંટણ"), ("knee", "घुटना"),
        ("pain", "દુખાવો"), ("pain", "दर्द"), ("cough", "ખાંસી"), ("cough", "खांसी"),
        ("itching", "ખંજવાળ"), ("itching", "खुजली"), ("weakness", "નબળાઈ"), ("weakness", "कमजोरी"),
        ("fatigue", "थकान"), ("thirst", "प्यास"), ("throat", "ગળું"), ("throat", "गला"),
        ("phlegm", "કફ"), ("phlegm", "बलगम"), ("chest", "છાતી"), ("chest", "छाती"),
        ("fever", "તાવ"), ("fever", "बुखार"), ("swelling", "સોજો"), ("swelling", "सूजन"),
        # Clinical concept alignments:
        ("appetite", "eat"), ("appetite", "food"), ("anorexia", "eat"), ("anorexia", "food"),
        ("appetite", "ભૂખ"), ("appetite", "ખાવા"), ("appetite", "भूख"), ("appetite", "खाना"),
        ("digestion", "stomach"), ("digestion", "food"), ("digestive", "stomach"),
        ("tongue", "taste"), ("mouth", "taste"), ("vomiting", "throw up"),
    ]
    hits = 0
    lower_answer = raw_answer.lower()
    val_lower = str(value).lower()
    for eng_like, match_target in synonym_groups:
        if eng_like in val_lower and match_target in lower_answer:
            hits += 1
    return hits


def classify_presentation_domain(text: str) -> str:
    if not text:
        return DOMAIN_GENERAL
    lower = text.lower()

    # Vernacular-first: a Gujarati/Hindi answer must not be mis-routed to an
    # unrelated domain (e.g. GU 'કમરમાં દુખાવો' -> musculoskeletal, not general).
    norm = normalize_regional_language(text)
    if norm["domain"]:
        return norm["domain"]

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
    denial_hint = ""
    norm = normalize_regional_language(new_answer)
    if not domain or domain == DOMAIN_GENERAL:
        # Check if chief complaint or new answer informs domain
        if norm["domain"]:
            domain = norm["domain"]
        else:
            detected = classify_presentation_domain(new_answer)
            if detected != DOMAIN_GENERAL:
                domain = detected
            elif getattr(session_like, "chief_complaint", None):
                detected = classify_presentation_domain(session_like.chief_complaint)
                if detected != DOMAIN_GENERAL:
                    domain = detected

    denied = getattr(session_like, "denied_concepts", []) or []
    denied_keys = sorted(denied_symptom_concept_keys(denied))
    if denied:
        denial_hint = (
            f"The patient explicitly denied these symptoms: {', '.join(denied)}. "
            "Do NOT ask about them again."
        )

    knowledge = get_domain_knowledge(domain)
    unanswered = [c for c in knowledge.relevant_concepts if c not in collected or not str(collected[c]).strip()]
    unanswered = [c for c in unanswered if c not in denied_keys]

    return {
        "patient": patient_info,
        "language": language,
        "current_answer": new_answer,
        "conversation_history": history,
        "asked_questions": asked_questions,
        "asked_concepts": asked_concepts,
        "collected_concepts": collected,
        "denied_concepts": denied_keys,
        "denial_hint": denial_hint,
        "concept_metadata": getattr(session_like, "concept_metadata", []) or [],
        "language_normalized_symptoms": norm["canonical_concepts"],
        "matched_vernacular_phrases": norm["matched_phrases"],
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
    if q_concept:
        if q_concept not in ALL_ALLOWED_CONCEPTS:
            reasons.append(f"Target concept '{q_concept}' is not in allowed concepts")
        elif domain != DOMAIN_GENERAL and q_concept not in knowledge.relevant_concepts and q_concept not in CORE_CLINICAL_CONCEPTS:
            reasons.append(f"Target concept '{q_concept}' is not in allowed concepts / not clinically relevant for {domain} presentation")
        elif q_concept in DOMAIN_INCOMPATIBLE_CONCEPTS.get(domain, set()):
            reasons.append(f"Target concept '{q_concept}' is not clinically compatible with the {domain} presentation")

    # Check H: Explicitly denied concepts are never re-asked as pending questions
    denied = getattr(session_like, "denied_concepts", []) or []
    denied_keys = denied_symptom_concept_keys(denied)
    if q_concept and q_concept in denied_keys:
        reasons.append(f"Target concept '{q_concept}' was explicitly denied by the patient ({denied})")

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
            # Check if existing value is sufficiently specific
            if _is_concept_value_specific(q_concept, str(existing_val)):
                reasons.append(f"Target concept '{q_concept}' is already answered with value '{existing_val}'")

    # Semantic Check: Does question text ask for an already-answered concept?
    # (Catches cases where LLM asked "How long have you had this?" but labelled target_concept="severity")
    SEMANTIC_CONCEPT_PATTERNS = {
        "duration": [
            r"\b(?:how long|how many (?:days|weeks|months|years|hours)|since when|when did it (?:start|begin))\b",
            r"(?:कितने समय|कितने दिनों|कब से|ક્યારથી|કેટલા સમય|કેટલા દિવસ)",
        ],
        "site": [
            r"\b(?:where on your body|which (?:part|area|joint|side)|location of)\b",
            r"(?:किस (?:जगह|भाग|हिस्से)|કયા (?:ભાગ|સાંધા))",
        ],
        "laterality": [
            r"\b(?:which side|one side or both|left or right)\b",
            r"(?:दायां या बायां|ડાબી કે જમણી)",
        ],
        "cough_character": [
            r"\b(?:dry (?:or|cough)|phlegm|mucus|bring up)\b",
            r"(?:सूखी या बलगम|સૂકી કે કફ)",
        ],
    }

    for c_name, patterns in SEMANTIC_CONCEPT_PATTERNS.items():
        if c_name in all_collected and _is_concept_value_specific(c_name, str(all_collected[c_name])):
            if status != "clarify":
                for pat in patterns:
                    if re.search(pat, q_text, re.IGNORECASE):
                        reasons.append(f"Question text targets '{c_name}' which is already answered ('{all_collected[c_name]}')")
                        break

    # Semantic Check: Does question text ask about an explicitly denied symptom?
    for d in denied:
        d_terms = [d]
        for lang_dict in NEGATED_SYMPTOM_TERMS.values():
            if d in lang_dict:
                d_terms.extend(lang_dict[d])
        for term in d_terms:
            if re.search(r"\b" + re.escape(term.lower()) + r"\b", q_lower) or term in q_text:
                # If question directly asks if they have the denied finding
                if status != "clarify" and any(w in q_lower or w in q_text for w in ["do you have", "any", "experience", "क्या", "શું"]):
                    reasons.append(f"Question text asks about explicitly denied symptom '{d}'")
                    break

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


def _is_concept_value_specific(concept: str, value: str) -> bool:
    """Check whether a collected concept value is already specific or needs clarification."""
    v = value.strip().lower()
    if not v:
        return False
    # Vague durations that justify clarification:
    if concept == "duration":
        vague_durations = {"recently", "few days", "some time", "a while", "not long", "हाल ही में", "થોડા દિવસથી"}
        if v in vague_durations:
            return False
    return True


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
# =========================================================================
# Human Fallback Question Library (All Concepts x en/hi/gu)
# =========================================================================
# Language-appropriate, empathetic, human-written fallback questions.
# Absolutely NEVER leaks internal concept identifiers (e.g. "laterality", "character").
HUMAN_FALLBACK_LIBRARY: Dict[str, Dict[str, str]] = {
    "primary_symptom": {
        "en": "What is the primary health problem or symptom bothering you today?",
        "hi": "आज आपको सबसे मुख्य परेशानी या लक्षण क्या महसूस हो रहा है?",
        "gu": "આજે તમને મુખ્ય તકલીફ કે લક્ષણ શું જણાય છે?",
    },
    "chief_complaint": {
        "en": "What is the main reason for your clinic visit today?",
        "hi": "आज क्लिनिक आने का आपका मुख्य कारण क्या है?",
        "gu": "આજે દવાખાને આવવાનું તમારું મુખ્ય કારણ શું છે?",
    },
    "site": {
        "en": "Which exact part or area of your body is affected?",
        "hi": "शरीर का कौन सा हिस्सा या जोड़ मुख्य रूप से प्रभावित है?",
        "gu": "શરીરનો કયો ભાગ કે સાંધો મુખ્યત્વે પ્રભાવિત છે?",
    },
    "laterality": {
        "en": "Does the problem affect one side, both sides, or both equally?",
        "hi": "क्या यह तकलीफ़ शरीर के एक तरफ है, दोनों तरफ, या दोनों में बराबर है?",
        "gu": "શું આ તકલીફ શરીરની એક બાજુ છે, બંને બાજુ, કે બંનેમાં સરખી છે?",
    },
    "duration": {
        "en": "How long have you been experiencing this issue?",
        "hi": "यह समस्या आपको कितने समय से हो रही है?",
        "gu": "આ સમસ્યા તમને કેટલા સમયથી થાય છે?",
    },
    "onset": {
        "en": "Did this start suddenly or gradually?",
        "hi": "क्या यह तकलीफ़ अचानक शुरू हुई थी या धीरे-धीरे बढ़ी?",
        "gu": "શું આ તકલીફ અચાનક શરૂ થઈ હતી કે ધીમે-ધીમે વધી?",
    },
    "severity": {
        "en": "How severe is the problem in your own words, and does it stop you from sleeping or resting?",
        "hi": "आपके शब्दों में यह परेशानी कितनी गंभीर है, और क्या इससे आपकी नींद या आराम में खलल पड़ता है?",
        "gu": "તમારા શબ્દોમાં આ તકલીફ કેટલી ગંભીર છે, અને શું તેનાથી ઊંઘ કે આરામમાં ખલેલ પહોંચે છે?",
    },
    "character": {
        "en": "How would you describe the sensation — is it burning, aching, throbbing, or a feeling of heaviness?",
        "hi": "तकलीफ़ का अहसास कैसा है — जलन, भारीपन, मीठा दर्द या चुभन जैसा?",
        "gu": "આ તકલીફનો અનુભવ કેવો છે — બળતરા, ભારેપણું, કળતર કે ખૂંચવા જેવો?",
    },
    "stiffness_or_swelling": {
        "en": "Have you noticed any swelling, morning stiffness, or warmth in the affected area?",
        "hi": "क्या उस हिस्से में सुबह के समय जकड़न, सूजन या गर्मी महसूस होती है?",
        "gu": "શું તે ભાગમાં સવારે જકડાઈ જવું, સોજો કે ગરમાવો લાગે છે?",
    },
    "functional_limitation": {
        "en": "Does this problem make it difficult to walk, move, or do your usual daily activities?",
        "hi": "क्या इस तकलीफ़ की वजह से चलने-फिरने या रोज़मर्रा के काम करने में कठिनाई होती है?",
        "gu": "શું આ તકલીફને લીધે હલનચલન કરવામાં કે રોજીંદા કામકાજ કરવામાં મુશ્કેલી પડે છે?",
    },
    "aggravating_factors": {
        "en": "What tends to make the problem worse, such as certain activities, movements, or foods?",
        "hi": "किस काम, हरकत या खाने-पीने से यह तकलीफ़ और बढ़ जाती है?",
        "gu": "કઈ પ્રવૃત્તિ, હલનચલન કે ખાવા-પીવાથી આ તકલીફ વધી જાય છે?",
    },
    "relieving_factors": {
        "en": "What seems to make it feel better, such as rest, warmth, or a specific position?",
        "hi": "आराम करने, गर्म सेंक या किसी खास स्थिति से क्या इसमें राहत मिलती है?",
        "gu": "આરામ કરવાથી, શેક કરવાથી કે કોઈ ખાસ સ્થિતિથી શું એમાં રાહત જણાય છે?",
    },
    "food_relationship": {
        "en": "Do your symptoms change after eating, on an empty stomach, or with specific foods?",
        "hi": "क्या खाना खाने के बाद, खाली पेट या किसी खास भोजन से तकलीफ़ में कोई बदलाव आता है?",
        "gu": "શું જમ્યા પછી, ભૂખ્યા પેટે કે કોઈ ખાસ ખોરાકથી લક્ષણોમાં ફેરફાર થાય છે?",
    },
    "bowel_habits": {
        "en": "Have you noticed changes in your digestion or bowel movements, such as constipation or looseness?",
        "hi": "क्या पेट साफ होने में कोई बदलाव, जैसे कब्ज या दस्त महसूस हुआ है?",
        "gu": "શું પેટ સાફ થવામાં કોઈ ફેરફાર, જેમ કે કબજિયાત કે ઝાડા જેવું જણાયું છે?",
    },
    "cough_character": {
        "en": "Is your cough dry, or does it bring up phlegm or mucus?",
        "hi": "क्या खांसी सूखी है या बलगम/कफ के साथ आती है?",
        "gu": "શું ખાંસી સૂકી છે કે કફ/ગળફા સાથે આવે છે?",
    },
    "itching_severity": {
        "en": "How troublesome is the itching or irritation on your skin?",
        "hi": "त्वचा पर खुजली या जलन आपको कितनी परेशान कर रही है?",
        "gu": "ચામડી પર ખંજવાળ કે બળતરા તમને કેટલી હેરાન કરે છે?",
    },
    "energy_and_thirst": {
        "en": "Have you noticed changes in your energy, unusual fatigue, thirst, or urination?",
        "hi": "क्या आपको अत्यधिक थकान, बार-बार प्यास लगना या पेशाब में कोई बदलाव महसूस हुआ है?",
        "gu": "શું તમને ખૂબ થાક, વારંવાર તરસ લાગવી કે પેશાબમાં કોઈ ફેરફાર જણાય છે?",
    },
    "associated_symptoms": {
        "en": "Are you noticing any other symptoms alongside this main complaint?",
        "hi": "क्या इस मुख्य समस्या के अलावा कोई अन्य लक्षण भी महसूस हो रहा है?",
        "gu": "શું આ મુખ્ય તકલીફ ઉપરાંત કોઈ અન્ય લક્ષણ પણ અનુભવાય છે?",
    },
    "triggers": {
        "en": "Did anything specific seem to trigger or bring on this problem?",
        "hi": "क्या किसी खास वजह, मौसम या बदलाव से यह तकलीफ़ शुरू हुई थी?",
        "gu": "શું કોઈ ચોક્કસ કારણ, હવામાન કે ફેરફારથી આ તકલીફ શરૂ થઈ હતી?",
    },
    "weight_changes": {
        "en": "Have you noticed any unintended change in your weight recently?",
        "hi": "क्या हाल ही में आपके वजन में कोई अनपेक्षित बदलाव आया है?",
        "gu": "શું તાજેતરમાં તમારા વજનમાં કોઈ અણધાર્યો ફેરફાર થયો છે?",
    },
    "previous_treatment": {
        "en": "Have you tried any home remedies, medications, or consulted a doctor for this before?",
        "hi": "क्या इसके लिए आपने पहले कोई दवाई, घरेलू उपाय या डॉक्टर से सलाह ली है?",
        "gu": "શું આ માટે તમે અગાઉ કોઈ દવા, ઘરગથ્થુ ઉપચાર કે ડૉક્ટરની સલાહ લીધી છે?",
    },
    "relevant_history": {
        "en": "Do you have any existing health conditions or past illnesses related to this?",
        "hi": "क्या आपको पहले से कोई अन्य बीमारी या पुरानी स्वास्थ्य समस्या है?",
        "gu": "શું તમને અગાઉથી કોઈ અન્ય બીમારી કે જૂની સ્વાસ્થ્ય સમસ્યા છે?",
    },
}

GENERAL_FALLBACK_QUESTIONS = HUMAN_FALLBACK_LIBRARY

# Last-resort fallback that never reveals internal concept names.
LEAK_SAFE_FALLBACKS: Dict[str, str] = {
    "en": "Could you tell us a little more about your symptoms in your own words?",
    "hi": "कृपया अपने लक्षणों के बारे में अपने शब्दों में थोड़ा और बताएँ।",
    "gu": "કૃપા કરીને તમારા લક્ષણો વિશે તમારા શબ્દોમાં થોડું વધુ જણાવો.",
}


def get_fallback_question(session_like: Any, target_concept: Optional[str] = None) -> Dict[str, str]:
    """Provide a deterministic fallback question when the LLM is unavailable or rejected.

    Ensures the kiosk never hangs, loops, or presents a blank screen.
    Selects in the patient's language ('en', 'hi', 'gu').
    Filters out already answered concepts, asked concepts, AND explicitly denied concepts.
    Uses human language only — NEVER robotic '{concept}' formatting.
    """
    domain = getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    knowledge = get_domain_knowledge(domain)
    language = getattr(session_like, "language", "en") or "en"
    if language not in ("en", "hi", "gu"):
        language = "en"

    collected = getattr(session_like, "collected_concepts", {}) or {}
    asked_concepts = getattr(session_like, "asked_concepts", []) or []
    denied = getattr(session_like, "denied_concepts", []) or []
    denied_keys = denied_symptom_concept_keys(denied)
    incompatible = DOMAIN_INCOMPATIBLE_CONCEPTS.get(domain, set())

    # Determine concept to ask
    chosen_concept = target_concept
    if (
        not chosen_concept
        or chosen_concept in asked_concepts
        or (chosen_concept in collected and collected[chosen_concept])
        or chosen_concept in denied_keys
        or chosen_concept in incompatible
    ):
        chosen_concept = None
        # Find first missing mandatory concept in priority order
        profile = get_presentation_profile(domain)
        priority_map = {qp.concept_key: qp.priority for qp in profile.question_sequence}
        sorted_mandatory = sorted(knowledge.mandatory_concepts, key=lambda c: priority_map.get(c, 999))
        for mc in sorted_mandatory:
            if (
                mc not in asked_concepts
                and (mc not in collected or not str(collected[mc]).strip())
                and mc not in denied_keys
                and mc not in incompatible
            ):
                chosen_concept = mc
                break

    if not chosen_concept:
        # Find first missing relevant concept
        for rc in knowledge.relevant_concepts:
            if (
                rc not in asked_concepts
                and (rc not in collected or not str(collected[rc]).strip())
                and rc not in denied_keys
                and rc not in incompatible
            ):
                chosen_concept = rc
                break

    if not chosen_concept:
        # Check all allowed concepts that aren't denied or incompatible
        for c in ALL_ALLOWED_CONCEPTS:
            if c not in asked_concepts and c not in denied_keys and c not in incompatible:
                chosen_concept = c
                break

    if not chosen_concept:
        chosen_concept = "primary_symptom"

    # Get question text from knowledge base fallback table first
    q_dict = knowledge.fallback_questions.get(chosen_concept)
    if not q_dict:
        # General human-readable fallback library
        q_dict = HUMAN_FALLBACK_LIBRARY.get(chosen_concept, {})

    text = q_dict.get(language) or q_dict.get("en")
    if not text:
        # Absolute last resort: safe generic phrasing, zero concept leak
        text = LEAK_SAFE_FALLBACKS.get(language, LEAK_SAFE_FALLBACKS["en"])

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
    denied = extract_denied_concepts(text)

    # 1. Duration extraction (English, Hindi, Gujarati)
    dur_match = re.search(
        r"\b(?:for|since|past|lasting)\s+(\d+\s*(?:days?|weeks?|months?|years?|hours?)|yesterday|today|(?:a|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?|years?))\b",
        lower
    )
    if not dur_match:
        dur_match = re.search(r"\b(\d+\s*(?:days?|weeks?|months?|years?))\b", lower)
    # Hindi duration: "पांच दिन से", "दो हफ्ते से", "छह महीने"
    if not dur_match:
        hi_dur = re.search(r"((?:[०-९\d]+|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस)\s*(?:दिन|हफ्ते|सप्ताह|महीने|महीनों|साल|वर्ष)(?:\s*से)?)", text)
        if hi_dur:
            extracted["duration"] = hi_dur.group(1).strip()
    # Gujarati duration: "ચાર દિવસથી", "પાંચ દિવસ", "બે અઠવાડિયાથી", "છ મહિના"
    if not dur_match and "duration" not in extracted:
        gu_dur = re.search(r"((?:[૦-૯\d]+|એક|બે|ત્રણ|ચાર|પાંચ|છ|સાત|આઠ|નવ|દસ)\s*(?:દિવસ|અઠવાડિયા|મહિના|વર્ષ)(?:થી)?)", text)
        if gu_dur:
            extracted["duration"] = gu_dur.group(1).strip()
    if dur_match and "duration" not in extracted:
        extracted["duration"] = dur_match.group(1).strip()

    # 2. Severity extraction
    sev_match = re.search(
        r"\b(mild|moderate|severe|unbearable|very severe|extremely painful|intense|sharp|dull|throbbing|aching|\d+\s*(?:out of|\/)\s*10)\b",
        lower
    )
    if sev_match:
        extracted["severity"] = sev_match.group(1).strip()
    elif "ખૂબ" in text or "તીવ્ર" in text or "બહુ" in text or "बहुत" in text or "तेज" in text or "तीव्र" in text:
        extracted["severity"] = "severe"

    # 3. Onset extraction
    onset_match = re.search(
        r"\b(?:started|began|onset)\s+(?:about\s+)?(\d+\s*(?:days?|weeks?|months?)\s*ago|yesterday|suddenly|gradually|last\s*(?:night|week|month))\b",
        lower
    )
    if not onset_match:
        onset_match = re.search(r"\b(\d+\s*(?:days?|weeks?|months?)\s*ago)\b", lower)
    if onset_match:
        extracted["onset"] = onset_match.group(1).strip()
    elif re.search(r"\b(suddenly|yesterday|gradually)\b", lower):
        m = re.search(r"\b(suddenly|yesterday|gradually)\b", lower)
        if m:
            extracted["onset"] = m.group(1).strip()
    elif "અચાનક" in text or "अचानक" in text:
        extracted["onset"] = "sudden"
    elif "ધીમે" in text or "धीरे" in text:
        extracted["onset"] = "gradual"

    # 4. Site & Anatomical location
    sites = [
        ("lower back", "lower back"), ("back", "back"), ("knee", "knee"), ("knees", "knee"),
        ("shoulder", "shoulder"), ("neck", "neck"), ("spine", "spine"),
        ("hip", "hip"), ("elbow", "elbow"), ("wrist", "wrist"), ("ankle", "ankle"),
        ("skin", "skin"), ("throat", "throat"), ("stomach", "stomach"), ("abdomen", "abdomen"),
        ("joints", "joints"), ("face", "face"), ("chest", "chest"), ("leg", "leg"), ("arm", "arm"),
        ("પેટ", "stomach"), ("કમર", "lower back"), ("ઘૂંટણ", "knee"), ("ગળું", "throat"), ("ત્વચા", "skin"), ("ચામડી", "skin"),
        ("पेट", "stomach"), ("कमर", "lower back"), ("घुटना", "knee"), ("गला", "throat"), ("त्वचा", "skin")
    ]
    for pattern, canonical_site in sites:
        if pattern in lower or pattern in text:
            extracted["site"] = canonical_site
            break

    # Laterality
    if re.search(r"\bleft\b", lower) or "ડાબી" in text or "बायां" in text or "बायें" in text:
        extracted["laterality"] = "left"
    elif re.search(r"\bright\b", lower) or "જમણી" in text or "दायां" in text or "दायें" in text:
        extracted["laterality"] = "right"
    elif re.search(r"\bboth\b", lower) or "બંને" in text or "दोनों" in text:
        extracted["laterality"] = "both"

    # 5. Aggravating factors
    agg_match = re.search(
        r"\b(?:worse|aggravated|hurts more|pain increases)\s+(?:when|with|after|on)\s+([a-zA-Z\s]+?)(?:[.,;]|$)",
        lower
    )
    if agg_match:
        extracted["aggravating_factors"] = agg_match.group(1).strip()
    elif "stairs" in lower or "દાદર" in text or "सीढ़ियां" in text or "सीढ़ी" in text:
        extracted["aggravating_factors"] = "stairs / climbing"

    # 6. Food relationship (Digestive)
    if re.search(r"\b(?:after meals?|on empty stomach|with spicy food|after eating)\b", lower):
        food_match = re.search(r"\b(?:after meals?|on empty stomach|with spicy food|after eating)\b", lower)
        if food_match:
            extracted["food_relationship"] = food_match.group(0).strip()
    elif "જમ્યા પછી" in text or "ખાધા પછી" in text or "ભોજન પછી" in text or "खाने के बाद" in text or "भोजन के बाद" in text:
        extracted["food_relationship"] = "worse after meals"

    # 7. Cough character (only if cough not denied)
    if "cough" not in denied and "phlegm" not in denied:
        cough_match = re.search(
            r"\b(dry cough|productive cough|wet cough|cough with phlegm|phlegm|mucus)\b",
            lower
        )
        if cough_match:
            extracted["cough_character"] = cough_match.group(1).strip()
        elif "सूखी खांसी" in text or "સૂકી ખાંસી" in text:
            extracted["cough_character"] = "dry cough"
        elif "कफ" in text or "बलगम" in text or "ગળફો" in text:
            extracted["cough_character"] = "cough with phlegm"

    # 8. Itching severity (only if dermatological domain or explicitly skin itch, not stomach burning!)
    is_skin_context = (
        domain == DOMAIN_DERMATOLOGICAL
        or "skin" in lower or "ત્વચા" in text or "ચામડી" in text or "त्वचा" in text or "rash" in lower
    )
    if "itching" not in denied:
        if is_skin_context:
            itch_match = re.search(
                r"\b(severe itching|intense itching|mild itching|itching and burning|burning sensation|itching)\b",
                lower
            )
            if itch_match:
                extracted["itching_severity"] = itch_match.group(1).strip()
            elif "ખંજવાળ" in text or "खुजली" in text:
                extracted["itching_severity"] = "itching"
        else:
            # Without skin context, only match if explicit itch word is used (never bare "burning sensation")
            itch_match = re.search(
                r"\b(severe itching|intense itching|mild itching|itching)\b",
                lower
            )
            if itch_match:
                extracted["itching_severity"] = itch_match.group(1).strip()
            elif "ખંજવાળ" in text or "खुजली" in text:
                extracted["itching_severity"] = "itching"

    # 9. Digestive burning / Epigastric
    if ("stomach" in lower or "પેટ" in text or "पेट" in text) and ("burning" in lower or "બળતરા" in text or "जलन" in text):
        extracted["primary_symptom"] = "burning sensation in the stomach"
        extracted["site"] = "stomach"

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
