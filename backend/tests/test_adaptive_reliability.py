"""Phase 1.7 conversational-reliability regression tests.

Covers the reliability hardening: regional-language canonical meaning,
explicit-negation (denied concept) handling, domain incompatibility, leak-safe
fallbacks, and the one-shot bounded LLM self-correction path.
"""
import json
import os
import re
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.routers.session as session_router
from backend.main import app
from backend.rules.adaptive_interview import (
    DOMAIN_DIGESTIVE,
    DOMAIN_GENERAL,
    DOMAIN_METABOLIC,
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    classify_presentation_domain,
    extract_denied_concepts,
    get_fallback_question,
    guess_synonym_overlap,
    normalize_regional_language,
    validate_llm_proposal,
)
from backend.services.llm_provider import correct_adaptive_turn, generate_adaptive_turn


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_reliability.db")
        os.environ["DATABASE_PATH"] = db_file
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start(client: TestClient, lang: str = "en", answer: str = "headache since yesterday") -> str:
    res = client.post(
        "/session/start",
        json={
            "patient": {"name": "Test", "age": 40, "gender": "female"},
            "language": lang,
            "visit_type": "adaptive",
            "adaptive": True,
            "use_adaptive": True,
        },
    )
    assert res.status_code == 200
    sid = res.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def _answer(client: TestClient, sid: str, text: str, proposal: dict):
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=proposal)):
        resp = client.post(f"/session/{sid}/answer", json={"answer": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _proposal(domain, concepts, q_text, q_concept, status="continue", denied=None):
    return {
        "case_update": {
            "presentation": domain,
            "concepts": concepts,
            "denied_concepts": denied or [],
            "mentioned_documents": [],
        },
        "next_question": (
            {"text": q_text, "target_concept": q_concept, "reason": "explore", "priority": "normal"}
            if q_text
            else None
        ),
        "status": status,
        "confidence": 0.9,
    }


def _dummy_session(domain=DOMAIN_MUSCULOSKELETAL, collected=None, asked=None, denied=None, count=0, language="en"):
    return SimpleNamespace(
        presentation_domain=domain,
        collected_concepts=collected or {},
        asked_concepts=asked or [],
        asked_questions=[],
        adaptive_question_count=count,
        denied_concepts=denied or [],
        language=language,
    )


def _proposal_namespace(concepts, q_text, q_concept, status="continue"):
    return SimpleNamespace(
        case_update=SimpleNamespace(concepts=concepts),
        next_question=SimpleNamespace(text=q_text, target_concept=q_concept, reason="r", priority="normal")
        if q_text
        else None,
        status=status,
    )


# ---------------------------------------------------------------------------
# Regional-language canonical meaning
# ---------------------------------------------------------------------------

def test_01_gujarati_stomach_burning_maps_to_digestive_domain():
    norm = normalize_regional_language("મારા પેટમાં બળતરા થાય છે")
    assert norm["domain"] == DOMAIN_DIGESTIVE
    assert norm["canonical_concepts"]


def test_02_hindi_stomach_burning_maps_to_digestive_domain():
    norm = normalize_regional_language("मेरे पेट में जलन हो रही है")
    assert norm["domain"] == DOMAIN_DIGESTIVE
    assert norm["canonical_concepts"]


def test_03_gujarati_knee_pain_routes_to_musculoskeletal_not_general():
    dom = classify_presentation_domain("મારા ઘૂંટણમાં દુખાવો થઈ રહ્યો છે")
    assert dom in (DOMAIN_MUSCULOSKELETAL, DOMAIN_GENERAL)
    # vernacular mapping wins: must not land on an unrelated domain
    assert dom != DOMAIN_RESPIRATORY


def test_04_guess_synonym_overlap_resolves_cross_language_synonyms():
    assert guess_synonym_overlap("stomach burning", "પેટમાં બળતરા") == 2
    assert guess_synonym_overlap("knee pain", "घुटने में दर्द") == 1  # only 'pain'→दर्द aligns ('घुटने'≠'घुटना')
    assert guess_synonym_overlap("cough", "খांसी") == 0  # unrelated script


# ---------------------------------------------------------------------------
# Explicit-negation (denied concept) extraction
# ---------------------------------------------------------------------------

def test_05_english_negation_extraction():
    denied = extract_denied_concepts("I have stomach pain but no fever and no vomiting")
    assert "fever" in denied
    assert "vomiting" in denied


def test_06_hindi_suffix_negation_extraction():
    denied = extract_denied_concepts("मुझे पेट दर्द है, बुखार नहीं है और उल्टी नहीं")
    assert "fever" in denied
    assert "vomiting" in denied


def test_07_gujarati_suffix_negation_extraction():
    denied = extract_denied_concepts("મને પેટમાં દુખાવો છે, તાવ નથી અને ઉધરસ નથી")
    assert "fever" in denied
    assert "cough" in denied


def test_08_gujarati_prefix_negation_extraction():
    denied = extract_denied_concepts("મને તાવ નથી, ઉધરસ પણ નથી")
    assert "fever" in denied
    assert "cough" in denied


# ---------------------------------------------------------------------------
# Validator: denied concepts, domain incompatibility
# ---------------------------------------------------------------------------

def test_09_validator_rejects_question_on_explicitly_denied_concept():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Do you also have a cough?", "cough_character"),
        _dummy_session(denied=["cough"]),
    )
    assert result.valid is False
    assert any("denied" in r for r in result.reasons)


def test_10_validator_rejects_domain_incompatible_concept_on_metabolic():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Does the pain feel sharp, dull, or burning?", "character"),
        _dummy_session(domain=DOMAIN_METABOLIC),
    )
    assert result.valid is False
    assert any("compatible" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Deterministic fallback: leak-safe, skips denied/asked concepts
# ---------------------------------------------------------------------------

def test_11_fallback_skips_asked_and_denied_and_never_leaks_concept_names():
    session = _dummy_session(
        domain=DOMAIN_MUSCULOSKELETAL,
        collected={},
        asked=["primary_symptom"],
        denied=["fever"],
    )
    fallback = get_fallback_question(session)
    target = fallback["target_concept"]
    assert target != "primary_symptom"
    assert not any(d in target for d in ("fever",))
    text = fallback["text"].lower()
    concept_words = target.replace("_", " ")
    assert concept_words not in text  # human language only, no concept-id leak
    assert fallback["text"].strip()


def test_12_fallback_selects_patient_language():
    for lang in ("en", "hi", "gu"):
        session = SimpleNamespace(
            presentation_domain=DOMAIN_GENERAL,
            collected_concepts={},
            asked_concepts=[],
            adaptive_question_count=0,
            denied_concepts=[],
            language=lang,
        )
        fallback = get_fallback_question(session)
        assert fallback["text"], lang


# ---------------------------------------------------------------------------
# Router end-to-end: correction path and denied-concept protection
# ---------------------------------------------------------------------------

def test_13_rejected_proposal_is_repaired_by_one_bounded_correction(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "My stomach burns after eating oily food.",
        _proposal(
            DOMAIN_DIGESTIVE,
            {"primary_symptom": "stomach burning", "food_relationship": "worse after oily food"},
            "Does the burning happen between meals too?",
            "severity",
        ),
    )
    assert first["needs_review"] is False

    corrected = _proposal(
        DOMAIN_DIGESTIVE,
        {"severity": "between meals"},
        "Did this burning start suddenly or gradually?",
        "onset",
    )
    blocked = _proposal(
        DOMAIN_DIGESTIVE,
        {"severity": "between meals"},
        "Does the burning happen between meals too?",
        "severity",
    )
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=blocked)), patch.object(
        session_router, "correct_adaptive_turn", AsyncMock(return_value=corrected)
    ):
        resp = client.post(f"/session/{sid}/answer", json={"answer": "Between meals."})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_review"] is False
    assert data["next_question"] == "Did this burning start suddenly or gradually?"
    assert data["session_complete"] is False


def test_14_denied_concept_never_reasked_and_correction_failure_falls_back(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "My stomach burns after eating oily food.",
        _proposal(
            DOMAIN_DIGESTIVE,
            {"primary_symptom": "stomach burning", "food_relationship": "worse after oily food"},
            "Does the burning happen between meals too?",
            "severity",
        ),
    )
    assert first["needs_review"] is False

    # LLM asks about a concept that maps to the denied symptom "fever"
    banned = _proposal(
        DOMAIN_DIGESTIVE,
        {"severity": "between meals"},
        "Do you also have any fever or vomiting?",
        "associated_symptoms",
    )
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=banned)), patch.object(
        session_router, "correct_adaptive_turn", AsyncMock(return_value=None)
    ):
        resp = client.post(
            f"/session/{sid}/answer",
            json={"answer": "Between meals. No fever."},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_review"] is True
    assert data["next_question"]
    assert "fever" not in data["next_question"].lower()
    assert data["session_complete"] is False


def test_15_continuation_after_stale_proposal_never_repeats_previous_question(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "My right knee hurts when I climb stairs.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "knee pain", "site": "right knee", "aggravating_factors": "climbing stairs"},
            "How long has this knee pain been present?",
            "duration",
        ),
    )
    assert first["needs_review"] is False

    stale = _proposal(
        DOMAIN_MUSCULOSKELETAL,
        {"duration": "about a week"},
        "Is climbing stairs still the main trigger?",
        "aggravating_factors",
    )
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=stale)), patch.object(
        session_router, "correct_adaptive_turn", AsyncMock(return_value=None)
    ):
        resp = client.post(f"/session/{sid}/answer", json={"answer": "About a week."})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_review"] is True
    assert data["next_question"] != "Is climbing stairs still the main trigger?"
    assert data["session_complete"] is False


# ---------------------------------------------------------------------------
# Phase 1.8: Gujarati/Hindi final-turn reliability
# Internal concept-name leakage & language-script mismatch on user-facing text.
# Observed defects: "Can you tell us more about your laterality?" (EN leak), and
# English questions served to Gujarati/Hindi sessions (garbled final turn).
# ---------------------------------------------------------------------------

def test_16_validator_rejects_internal_concept_name_leak():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Can you tell us more about your laterality?", "laterality"),
        _dummy_session(),
    )
    assert result.valid is False
    assert any("internal concept" in r for r in result.reasons)


def test_17_validator_rejects_phrase_concept_leak():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Can you tell us more about your functional limitation?", "functional_limitation"),
        _dummy_session(),
    )
    assert result.valid is False
    assert any("internal concept" in r for r in result.reasons)


def test_18_validator_rejects_english_question_in_gujarati_session():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Can you tell us more about your triggers?", "triggers"),
        _dummy_session(language="gu"),
    )
    assert result.valid is False
    assert any("patient's language" in r for r in result.reasons)


def test_19_validator_rejects_english_question_in_hindi_session():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Can you tell us more about your onset?", "onset"),
        _dummy_session(language="hi"),
    )
    assert result.valid is False
    assert any("patient's language" in r for r in result.reasons)


def test_20_validator_accepts_natural_gujarati_question_in_gujarati_session():
    result = validate_llm_proposal(
        _proposal_namespace(
            {},
            "શું જમ્યા પછી, ભૂખ્યા પેટે કે કોઈ ખાસ ખોરાકથી લક્ષણોમાં ફેરફાર થાય છે?",
            "food_relationship",
        ),
        _dummy_session(domain=DOMAIN_DIGESTIVE, language="gu"),
    )
    assert result.valid is True


def test_21_validator_accepts_natural_hindi_question_in_hindi_session():
    result = validate_llm_proposal(
        _proposal_namespace({}, "क्या इस तकलीफ की वजह से चलने-फिरने में कठिनाई होती है?", "functional_limitation"),
        _dummy_session(language="hi"),
    )
    assert result.valid is True


def test_22_garbled_english_proposal_in_gujarati_session_falls_back_to_natural_gujarati(client):
    sid = _start(client, lang="gu", answer="મારા પેટમાં ખૂબ બળતરા થાય છે")
    garbled = _proposal(
        DOMAIN_DIGESTIVE,
        {"primary_symptom": "burning stomach"},
        "Can you tell us more about your triggers?",
        "triggers",
    )
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=garbled)), patch.object(
        session_router, "correct_adaptive_turn", AsyncMock(return_value=None)
    ):
        resp = client.post(f"/session/{sid}/answer", json={"answer": "જમ્યા પછી બળતરા વધે છે."})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_review"] is True
    assert re.search(r"[\u0A80-\u0AFF]", data["next_question"]), data["next_question"]
    assert data["session_complete"] is False