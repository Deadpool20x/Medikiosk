"""Adaptive Case-Taking Engine Foundation (Phase 1).

NOTE: The presentation profiles and question policies defined here are
ENGINEERING PILOT PATHWAYS for intake demonstration, NOT clinically validated
Ayurvedic diagnosis or treatment protocols. The engine is strictly an
intake and structured history-gathering tool.

Architectural Invariants:
1. Deterministic Control: Progression, sufficiency, and stopping conditions
   are governed 100% by deterministic code, NEVER by an LLM prompt.
2. Authoritative Safety: Red-flag screening (backend.rules.safety_rules)
   executes BEFORE any adaptive routing or question evaluation.
3. Multi-Concept Awareness: Single answers containing multiple clinical
   concepts (e.g., "knee pain for 2 weeks, worse on stairs") populate all
   matched concepts at once and avoid redundant questions.
4. Hard Question Cap: Under no circumstances does the kiosk ask more than
   MAX_ADAPTIVE_QUESTIONS (default: 5) per session.
5. Backward Compatibility: All legacy session fields (chief_complaint, HPI,
   answer_records, doctor reviews D01-D04) are continuously populated.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
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
    "onset",
    "duration",
    "severity",
    "character",
    "associated_symptoms",
    "aggravating_factors",
    "relieving_factors",
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

@dataclass
class QuestionPolicy:
    concept_key: str
    question_text: str
    priority: int
    required: bool = False
    legacy_field: Optional[str] = None


@dataclass
class PresentationProfile:
    domain_id: str
    display_name: str
    triggers: List[str]
    required_concepts: List[str]
    question_sequence: List[QuestionPolicy]
    max_questions: int = MAX_ADAPTIVE_QUESTIONS
    min_concepts: int = MIN_CORE_CONCEPTS


# Domain profiles definition
PRESENTATION_PROFILES: Dict[str, PresentationProfile] = {
    DOMAIN_MUSCULOSKELETAL: PresentationProfile(
        domain_id=DOMAIN_MUSCULOSKELETAL,
        display_name="Musculoskeletal & Joint Presentation (Pilot)",
        triggers=[
            "back pain", "lower back", "knee", "joint", "shoulder", "neck pain",
            "stiffness", "sprain", "swelling in joint", "arthritis", "sciatica",
            "muscle ache", "leg pain", "hip pain", "spine", "cervical", "lumbar",
            "sandhigata", "amavata", "kati", "janu", "greeva"
        ],
        required_concepts=["primary_symptom", "site", "duration"],
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What is the primary joint or muscle issue you are experiencing?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="site",
                question_text="Which specific joints or body areas are affected?",
                priority=2,
                required=True,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="onset",
                question_text="When did this joint or muscle discomfort first begin?",
                priority=3,
                required=False,
                legacy_field="onset",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How long has it been troubling you, and is it worse at specific times such as mornings?",
                priority=4,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="aggravating_factors",
                question_text="Does movement, bending, lifting, or walking make it worse?",
                priority=5,
                required=False,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="severity",
                question_text="On a scale of 1 to 10, how intense is the pain or stiffness?",
                priority=6,
                required=False,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Do you notice any swelling, clicking sounds, numbness, or morning stiffness?",
                priority=7,
                required=False,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
    DOMAIN_RESPIRATORY: PresentationProfile(
        domain_id=DOMAIN_RESPIRATORY,
        display_name="Respiratory Presentation (Pilot)",
        triggers=[
            "cough", "phlegm", "congestion", "cold", "runny nose", "sneezing",
            "sore throat", "wheeze", "wheezing", "asthma", "sinus", "breath",
            "kasa", "shwasa", "pratishyaya", "throat irritation"
        ],
        required_concepts=["primary_symptom", "duration", "cough_character"],
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What respiratory or throat symptoms are you experiencing?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How many days or weeks have you had this cough or congestion?",
                priority=2,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="cough_character",
                question_text="Is the cough dry, or is there phlegm/mucus? If phlegm, what color?",
                priority=3,
                required=True,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="onset",
                question_text="Did this start after exposure to cold weather, dust, or an illness?",
                priority=4,
                required=False,
                legacy_field="onset",
            ),
            QuestionPolicy(
                concept_key="severity",
                question_text="How severe is this discomfort, and does it interrupt your sleep at night?",
                priority=5,
                required=False,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Are you having any mild fever, body ache, headache, or throat pain?",
                priority=6,
                required=False,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
    DOMAIN_DIGESTIVE: PresentationProfile(
        domain_id=DOMAIN_DIGESTIVE,
        display_name="Digestive & Gastrointestinal Presentation (Pilot)",
        triggers=[
            "stomach pain", "acidity", "gas", "bloating", "constipation", "diarrhea",
            "loose motion", "heartburn", "indigestion", "nausea", "loss of appetite",
            "vomiting", "burping", "belching", "ajirna", "agnimandya", "amlapitta", "chardi"
        ],
        required_concepts=["primary_symptom", "duration", "food_relationship"],
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What digestive or stomach issue is bothering you most?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How long have you noticed these digestive symptoms?",
                priority=2,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="food_relationship",
                question_text="Do your symptoms get worse after meals, on an empty stomach, or with spicy foods?",
                priority=3,
                required=True,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="bowel_habits",
                question_text="Have you noticed any change in your bowel movements, like constipation or looseness?",
                priority=4,
                required=False,
                legacy_field="associated_symptoms",
            ),
            QuestionPolicy(
                concept_key="severity",
                question_text="How severe is the discomfort or burning sensation?",
                priority=5,
                required=False,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Are you also feeling nauseous, bloated, or having sour burps?",
                priority=6,
                required=False,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
    DOMAIN_DERMATOLOGICAL: PresentationProfile(
        domain_id=DOMAIN_DERMATOLOGICAL,
        display_name="Dermatological Presentation (Pilot)",
        triggers=[
            "skin", "rash", "itching", "boil", "eczema", "red patch", "psoriasis",
            "dry skin", "blister", "pimples", "acne", "fungal", "ringworm",
            "kushta", "kandu", "twak"
        ],
        required_concepts=["primary_symptom", "site", "duration"],
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What skin changes or irritation have you observed?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="site",
                question_text="Where on your body is the rash or irritation located?",
                priority=2,
                required=True,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How long has this skin condition been present?",
                priority=3,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="itching_severity",
                question_text="Is there significant itching, burning sensation, or flaking?",
                priority=4,
                required=False,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="triggers",
                question_text="Have you used any new soaps, creams, cosmetics, or medicines recently?",
                priority=5,
                required=False,
                legacy_field="onset",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Is there any fluid weeping, oozing, or warmth in the affected area?",
                priority=6,
                required=False,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
    DOMAIN_METABOLIC: PresentationProfile(
        domain_id=DOMAIN_METABOLIC,
        display_name="Metabolic & General Wellness Presentation (Pilot)",
        triggers=[
            "sugar", "diabetes", "thirst", "frequent urination", "weight gain",
            "weight loss", "thyroid", "fatigue", "tiredness", "exhaustion",
            "lethargy", "prameha", "sthaulya", "medoroga"
        ],
        required_concepts=["primary_symptom", "duration", "associated_symptoms"],
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What metabolic or energy concerns are you facing?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How long have you been noticing these changes in your body or energy?",
                priority=2,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="energy_and_thirst",
                question_text="Have you experienced unusual thirst, hunger, or changes in how often you urinate?",
                priority=3,
                required=False,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="weight_changes",
                question_text="Have you had any unintended weight gain or weight loss recently?",
                priority=4,
                required=False,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Do you also feel daytime drowsiness, weakness, or swelling in your feet?",
                priority=5,
                required=True,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
DOMAIN_GENERAL: PresentationProfile(
        domain_id=DOMAIN_GENERAL,
        display_name="General Presentation (Pilot)",
        triggers=[],
        required_concepts=[
            "primary_symptom", "onset", "duration", "severity", "character", "associated_symptoms",
        ],
        max_questions=6,
        min_concepts=6,
        question_sequence=[
            QuestionPolicy(
                concept_key="primary_symptom",
                question_text="What is the primary reason for your visit today?",
                priority=1,
                required=True,
                legacy_field="chief_complaint",
            ),
            QuestionPolicy(
                concept_key="onset",
                question_text="When did these symptoms first begin?",
                priority=2,
                required=False,
                legacy_field="onset",
            ),
            QuestionPolicy(
                concept_key="duration",
                question_text="How long have you been experiencing this, and is it constant or intermittent?",
                priority=3,
                required=True,
                legacy_field="duration",
            ),
            QuestionPolicy(
                concept_key="severity",
                question_text="On a scale of 1 to 10 or in your own words, how severe is the pain or discomfort?",
                priority=4,
                required=True,
                legacy_field="severity",
            ),
            QuestionPolicy(
                concept_key="character",
                question_text="Can you describe what the symptom feels like (e.g., sharp, dull, throbbing, aching)?",
                priority=5,
                required=False,
                legacy_field="character",
            ),
            QuestionPolicy(
                concept_key="associated_symptoms",
                question_text="Are you experiencing any other symptoms, such as fever, nausea, dizziness, or fatigue?",
                priority=6,
                required=False,
                legacy_field="associated_symptoms",
            ),
        ],
    ),
}

# Aliases for compatibility
PRESENTATION_DOMAINS = PRESENTATION_PROFILES

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
        profile = PRESENTATION_PROFILES[dom_key]
        for trigger in profile.triggers:
            if trigger in lower:
                return dom_key

    return DOMAIN_GENERAL


def get_presentation_profile(domain_id: Optional[str]) -> PresentationProfile:
    if domain_id and domain_id in PRESENTATION_PROFILES:
        return PRESENTATION_PROFILES[domain_id]
    return PRESENTATION_PROFILES[DOMAIN_GENERAL]


def evaluate_sufficiency(session_like: Any) -> bool:
    domain = getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    profile = get_presentation_profile(domain)
    
    question_count = getattr(session_like, "adaptive_question_count", 0)
    if question_count >= profile.max_questions:
        return True

    collected = getattr(session_like, "collected_concepts", {}) or {}

    has_all_required = all(
        (req in collected and collected[req] is not None and str(collected[req]).strip() != "")
        for req in profile.required_concepts
    )

    if question_count >= 2 and has_all_required and len(collected) >= profile.min_concepts:
        return True

    if select_next_question(session_like) is None:
        return True

    return False


def select_next_question(session_like: Any) -> Optional[Dict[str, Any]]:
    if getattr(session_like, "interview_complete", False):
        return None

    domain = getattr(session_like, "presentation_domain", None) or DOMAIN_GENERAL
    profile = get_presentation_profile(domain)

    question_count = getattr(session_like, "adaptive_question_count", 0)
    if question_count >= profile.max_questions:
        return None

    collected = getattr(session_like, "collected_concepts", {}) or {}
    asked_questions = getattr(session_like, "asked_questions", []) or []

    sorted_policies = sorted(profile.question_sequence, key=lambda q: q.priority)

    for policy in sorted_policies:
        val = collected.get(policy.concept_key)
        if val is not None and str(val).strip() != "":
            continue

        if policy.concept_key in ("chief_complaint", "onset", "duration", "severity", "character", "associated_symptoms"):
            leg_val = _get_legacy_field_value(session_like, policy.concept_key)
            if leg_val is not None and str(leg_val).strip() != "":
                continue

        if policy.concept_key in ("primary_symptom", "complaint") and getattr(session_like, "chief_complaint", None):
            continue

        if policy.question_text in asked_questions:
            continue

        return {
            "concept_key": policy.concept_key,
            "question_text": policy.question_text,
            "domain": profile.domain_id,
            "legacy_field": policy.legacy_field,
        }

    return None


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
        "joints", "face", "hands", "feet", "chest"
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


def _get_legacy_field_value(session_like: Any, field_name: str) -> Optional[Any]:
    if field_name == "chief_complaint":
        return getattr(session_like, "chief_complaint", None)
    hpi = getattr(session_like, "history_of_present_illness", None)
    if not hpi:
        return None
    if hasattr(hpi, field_name):
        return getattr(hpi, field_name)
    if isinstance(hpi, dict):
        return hpi.get(field_name)
    return None


def bridge_concepts_to_legacy(session_like: Any) -> None:
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
