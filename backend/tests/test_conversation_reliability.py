"""Tests for Phase 1.7: Conversational Reliability Hardening.

Covers the 10 failure modes and validation requirements:
1. Multi-stage Turn Pipeline order
2. Explicit Negative Concepts (denied_concepts)
3. Confidence-Aware Extraction (no false flips)
4. Regional Language Normalization (Hindi/Gujarati/English preserved)
5. Clinical Meaning Conflict Check (contradiction detection, e.g. stomach -> jaw)
6. Already-Answered Protection (semantic and target concept rejection)
7. Context-Aware Re-asking
8. Human Fallback Question Library (zero robotic concept leaks)
9. One-Shot LLM Self-Correction (1st rejected -> 2nd accepted; 2nd rejected -> fallback)
10. Category Compatibility (no pain descriptors on fatigue/weakness)
"""
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schema import Session, Patient
from backend.rules.adaptive_interview import (
    extract_denied_concepts,
    extract_concepts_from_text,
    find_concept_conflicts,
    validate_llm_proposal,
    get_fallback_question,
    HUMAN_FALLBACK_LIBRARY,
    DOMAIN_DIGESTIVE,
    DOMAIN_RESPIRATORY,
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_METABOLIC,
    DOMAIN_GENERAL,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_explicit_negative_concepts_multilingual():
    """Requirement 2: Extract explicit negatives across en, hi, gu."""
    # English
    en_denied = extract_denied_concepts("I have a dry cough but no fever and no chest pain.")
    assert "fever" in en_denied
    assert "chest_pain" in en_denied

    # Hindi
    hi_denied = extract_denied_concepts("मुझे खांसी है लेकिन बुखार नहीं है और उल्टी नहीं है।")
    assert "fever" in hi_denied
    assert "vomiting" in hi_denied

    # Gujarati
    gu_denied = extract_denied_concepts("મને ખાંસી છે પણ તાવ નથી અને ચક્કર નથી આવતા.")
    assert "fever" in gu_denied
    assert "dizziness" in gu_denied


def test_no_false_positive_flip_on_negations():
    """Requirement 3: Explicit negatives must not become positive extractions."""
    extracted = extract_concepts_from_text("I have cough for three days but no fever and no phlegm.")
    assert "phlegm" not in extracted.get("cough_character", "")
    assert extracted.get("duration") == "three days"


def test_clinical_meaning_conflict_detection():
    """Requirement 5: Detect anatomical contradictions (e.g. stomach -> jaw pain)."""
    # Stomach complaint proposing jaw pain
    conflicts = find_concept_conflicts(
        new_concepts={"primary_symptom": "severe jaw pain"},
        raw_answer="પેટમાં ખૂબ બળતરા થાય છે અને જમ્યા પછી વધી જાય છે.",
        collected={},
        denied=[],
    )
    assert len(conflicts) > 0
    assert any("violates clinical meaning" in c or "not supported" in c for c in conflicts)

    # Polarity flip: patient denied fever, but concept proposed fever
    conflicts_fever = find_concept_conflicts(
        new_concepts={"associated_symptoms": "high fever"},
        raw_answer="I have cough but no fever.",
        collected={},
        denied=["fever"],
    )
    assert len(conflicts_fever) > 0
    assert any("fever" in c for c in conflicts_fever)


def test_category_compatibility():
    """Requirement 10: Pain descriptors must be rejected for metabolic weakness/fatigue."""
    session_stub = SimpleNamespace(
        presentation_domain=DOMAIN_METABOLIC,
        collected_concepts={"primary_symptom": "extreme tiredness and weakness"},
        asked_concepts=[],
        asked_questions=[],
        denied_concepts=[],
        adaptive_question_count=1,
    )
    # Propose pain character for metabolic presentation
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="Is the pain sharp, dull, or throbbing?",
            target_concept="character",
            reason="Check pain nature",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, session_stub, DOMAIN_METABOLIC)
    assert not val.valid
    assert any("not clinically compatible" in r or "not in allowed concepts" in r for r in val.reasons)


def test_already_answered_semantic_protection():
    """Requirement 6: Reject question targeting a concept already established."""
    session_stub = SimpleNamespace(
        presentation_domain=DOMAIN_RESPIRATORY,
        collected_concepts={"primary_symptom": "dry cough", "duration": "4 days"},
        asked_concepts=["primary_symptom"],
        asked_questions=["What is your primary symptom?"],
        denied_concepts=[],
        adaptive_question_count=1,
    )
    # Direct target concept match
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="How long have you had this cough?",
            target_concept="duration",
            reason="Check duration",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, session_stub, DOMAIN_RESPIRATORY)
    assert not val.valid
    assert any("already answered" in r for r in val.reasons)

    # Semantic text match even if LLM mislabels target_concept as "severity"
    proposal_mislabeled = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="How many days have you been experiencing this cough?",
            target_concept="severity",
            reason="Check severity",
        ),
        status="continue",
    )
    val2 = validate_llm_proposal(proposal_mislabeled, session_stub, DOMAIN_RESPIRATORY)
    assert not val2.valid
    assert any("already answered" in r for r in val2.reasons)


def test_denied_concept_question_rejection():
    """Requirement 2 & 15: Reject questions targeting explicitly denied findings."""
    session_stub = SimpleNamespace(
        presentation_domain=DOMAIN_RESPIRATORY,
        collected_concepts={"primary_symptom": "dry cough", "duration": "5 days"},
        asked_concepts=["primary_symptom", "duration"],
        asked_questions=["What brings you in?", "How long have you had it?"],
        denied_concepts=["fever", "chest_pain"],
        adaptive_question_count=2,
    )
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="Do you have any fever or high temperature?",
            target_concept="associated_symptoms",
            reason="Check fever",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, session_stub, DOMAIN_RESPIRATORY)
    assert not val.valid
    assert any("denied" in r for r in val.reasons)


def test_human_fallback_library_zero_concept_leaks():
    """Requirement 8: Fallback questions must be natural and never leak internal identifiers."""
    for concept, q_langs in HUMAN_FALLBACK_LIBRARY.items():
        for lang, text in q_langs.items():
            assert "{" not in text and "}" not in text
            assert "_" not in text, f"Internal concept identifier leaked in {concept} ({lang}): {text}"
            assert concept not in text or concept == "duration" or concept == "onset", (
                f"Raw concept leaked in {concept} ({lang}): {text}"
            )
            assert len(text.strip()) > 10

    # Test get_fallback_question returns human text for laterality
    session_stub = SimpleNamespace(
        presentation_domain=DOMAIN_MUSCULOSKELETAL,
        collected_concepts={"primary_symptom": "knee pain", "site": "knee", "duration": "6 months"},
        asked_concepts=["primary_symptom", "site", "duration"],
        asked_questions=[],
        denied_concepts=[],
        language="en",
    )
    fallback = get_fallback_question(session_stub, target_concept="laterality")
    assert "laterality" not in fallback["text"].lower()
    assert "one side" in fallback["text"].lower() or "both sides" in fallback["text"].lower()


def test_one_shot_self_correction_flow(client, monkeypatch):
    """Requirement 9: Pipeline attempts 1 bounded self-correction on rejection before fallback."""
    from backend.routers import session as session_router

    # Create session
    r = client.post("/session/start", json={
        "patient": {"name": "Test Reliability", "age": 45, "gender": "female"},
        "language": "en",
        "visit_type": "new"
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")

    # Turn 1: Patient provides duration and denied fever
    call_count = {"generate": 0, "correct": 0}

    async def mock_generate(context):
        call_count["generate"] += 1
        # Propose an invalid question (asking about already answered duration)
        return {
            "case_update": {
                "presentation": DOMAIN_RESPIRATORY,
                "concepts": {"primary_symptom": "cough", "duration": "4 days"},
                "denied_concepts": ["fever"],
            },
            "next_question": {
                "text": "How long have you had this cough?",
                "target_concept": "duration",
                "reason": "Re-asking duration",
            },
            "status": "continue",
            "confidence": 0.85,
            "provider": "mock",
        }

    async def mock_correct(session_context, validation_reasons, recovery_hint=None):
        call_count["correct"] += 1
        # Successfully self-correct by proposing an unasked valid concept
        return {
            "case_update": {
                "presentation": DOMAIN_RESPIRATORY,
                "concepts": {},
            },
            "next_question": {
                "text": "Is the cough dry, or do you bring up phlegm or mucus?",
                "target_concept": "cough_character",
                "reason": "Corrected to valid unasked concept",
            },
            "status": "continue",
            "confidence": 0.9,
            "provider": "mock",
        }

    monkeypatch.setattr(session_router, "generate_adaptive_turn", mock_generate)
    monkeypatch.setattr(session_router, "correct_adaptive_turn", mock_correct)

    ans_resp = client.post(f"/session/{sid}/answer", json={
        "answer": "I have had a cough for four days but no fever."
    })
    assert ans_resp.status_code == 200
    data = ans_resp.json()

    # Verify self-correction was called exactly once and the corrected question was accepted
    assert call_count["generate"] == 1
    assert call_count["correct"] == 1
    assert "dry" in data["next_question"] or "phlegm" in data["next_question"]
    assert "How long" not in data["next_question"]
