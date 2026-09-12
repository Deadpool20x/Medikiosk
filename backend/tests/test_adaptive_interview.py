"""Tests for Adaptive Case-Taking Engine Foundation (Phase 1).

Tests A through O verify the core architectural invariants:
- Deterministic engine authority (LLM never controls state or stopping)
- Domain classification across the 6 pilot presentation profiles
- Multi-concept extraction and redundancy avoidance
- Bounded sufficiency and hard 5-question cap
- Authoritative safety screening execution
- Graceful handling of LLM null/failure states without stalling
- Backward compatibility and legacy field bridging
"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.models.schema import Session, HistoryOfPresentIllness, DoctorReview, Patient
from backend.rules.adaptive_interview import (
    classify_presentation_domain,
    get_presentation_profile,
    evaluate_sufficiency,
    select_next_question,
    extract_concepts_from_text,
    extract_concepts_from_payload,
    bridge_concepts_to_legacy,
    MAX_ADAPTIVE_QUESTIONS,
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    DOMAIN_DIGESTIVE,
    DOMAIN_DERMATOLOGICAL,
    DOMAIN_METABOLIC,
    DOMAIN_GENERAL,
    PRESENTATION_PROFILES,
)
from backend.db import get_session as db_get_session, save_session as db_save_session, init_db


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "adaptive_test.db")
        os.environ["DATABASE_PATH"] = db_path
        init_db()
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start_adaptive_session(client, name="Adaptive Patient", complaint="knee pain"):
    resp = client.post("/session/start", json={
        "patient": {"name": name, "age": 45, "gender": "female"},
        "language": "en",
        "visit_type": "adaptive",
        "adaptive": True,
    })
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    consent_resp = client.post(f"/session/{sid}/consent", json={"consent_given": True})
    assert consent_resp.status_code == 200
    client.post(f"/session/{sid}/patient-code")
    return sid


# =========================================================================
# TEST A: Back pain classifies Musculoskeletal
# =========================================================================
def test_a_back_pain_classifies_musculoskeletal():
    text = "I have had severe lower back pain and stiffness since yesterday"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_MUSCULOSKELETAL
    profile = get_presentation_profile(domain)
    assert profile.domain_id == DOMAIN_MUSCULOSKELETAL
    assert "site" in profile.required_concepts


# =========================================================================
# TEST B: Knee pain with duration skips duration question
# =========================================================================
def test_b_knee_pain_with_duration_skips_duration_question():
    text = "Severe knee pain for 3 weeks"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_MUSCULOSKELETAL

    concepts = extract_concepts_from_text(text, domain=domain)
    assert concepts.get("site") == "knee"
    assert concepts.get("duration") == "3 weeks"

    # Create session state with duration already filled
    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_MUSCULOSKELETAL,
        adaptive_question_count=1,
        collected_concepts={
            "primary_symptom": "knee pain",
            "site": "knee",
            "duration": "3 weeks",
        },
        asked_questions=["What is the primary joint or muscle area causing you discomfort?"],
        chief_complaint="knee pain",
        history_of_present_illness=HistoryOfPresentIllness(duration="3 weeks"),
    )

    next_q = select_next_question(dummy_session)
    assert next_q is not None
    # Next question must NOT be the duration question
    assert next_q["concept_key"] != "duration"
    assert "How long have you had this pain" not in next_q["question_text"]


# =========================================================================
# TEST C: Digestive presentation follows digestive policy
# =========================================================================
def test_c_digestive_presentation_follows_digestive_policy():
    text = "I am suffering from severe acidity and stomach pain after meals"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_DIGESTIVE
    profile = get_presentation_profile(domain)
    assert profile.domain_id == DOMAIN_DIGESTIVE
    assert "food_relationship" in profile.required_concepts

    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_DIGESTIVE,
        adaptive_question_count=1,
        collected_concepts={"primary_symptom": "acidity and stomach pain"},
        asked_questions=["What digestive or stomach issue is bothering you most?"],
        chief_complaint="acidity and stomach pain",
        history_of_present_illness=HistoryOfPresentIllness(),
    )
    next_q = select_next_question(dummy_session)
    assert next_q is not None
    assert next_q["domain"] == DOMAIN_DIGESTIVE


# =========================================================================
# TEST D: Skin rash follows dermatological policy
# =========================================================================
def test_d_skin_rash_follows_dermatological_policy():
    text = "Red itchy rash on my arms with severe itching"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_DERMATOLOGICAL
    profile = get_presentation_profile(domain)
    assert profile.domain_id == DOMAIN_DERMATOLOGICAL

    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_DERMATOLOGICAL,
        adaptive_question_count=0,
        collected_concepts={},
        asked_questions=[],
        chief_complaint=None,
        history_of_present_illness=HistoryOfPresentIllness(),
    )
    next_q = select_next_question(dummy_session)
    assert next_q is not None
    assert next_q["domain"] == DOMAIN_DERMATOLOGICAL
    assert "skin" in next_q["question_text"].lower() or "irritation" in next_q["question_text"].lower()


# =========================================================================
# TEST E: Respiratory presentation follows respiratory policy
# =========================================================================
def test_e_respiratory_presentation_follows_respiratory_policy():
    text = "Dry cough and running nose with throat irritation"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_RESPIRATORY
    profile = get_presentation_profile(domain)
    assert profile.domain_id == DOMAIN_RESPIRATORY
    assert "cough_character" in [q.concept_key for q in profile.question_sequence]


# =========================================================================
# TEST F: General / unclear presentation follows general policy
# =========================================================================
def test_f_general_unclear_presentation_follows_general_policy():
    text = "I feel slightly off and dizzy when getting out of bed"
    domain = classify_presentation_domain(text)
    assert domain == DOMAIN_GENERAL
    profile = get_presentation_profile(domain)
    assert profile.domain_id == DOMAIN_GENERAL


# =========================================================================
# TEST G: Distinct complaints yield distinct question sequences
# =========================================================================
def test_g_distinct_complaints_yield_distinct_question_sequences():
    profile_msk = get_presentation_profile(DOMAIN_MUSCULOSKELETAL)
    profile_dig = get_presentation_profile(DOMAIN_DIGESTIVE)
    profile_derm = get_presentation_profile(DOMAIN_DERMATOLOGICAL)

    keys_msk = [q.concept_key for q in profile_msk.question_sequence]
    keys_dig = [q.concept_key for q in profile_dig.question_sequence]
    keys_derm = [q.concept_key for q in profile_derm.question_sequence]

    assert keys_msk != keys_dig
    assert keys_dig != keys_derm
    assert "aggravating_factors" in keys_msk
    assert "food_relationship" in keys_dig
    assert "itching_severity" in keys_derm


# =========================================================================
# TEST H: Multi-concept extraction avoids re-asking
# =========================================================================
def test_h_multi_concept_extraction_avoids_reasking():
    text = "My lower back pain started 2 weeks ago and it is severe 8/10"
    extracted = extract_concepts_from_text(text, domain=DOMAIN_MUSCULOSKELETAL)
    assert extracted.get("site") == "lower back"
    assert extracted.get("duration") == "2 weeks"
    assert "8/10" in extracted.get("severity") or "severe" in extracted.get("severity")

    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_MUSCULOSKELETAL,
        adaptive_question_count=1,
        collected_concepts={
            "primary_symptom": "lower back pain",
            "site": "lower back",
            "duration": "2 weeks",
            "severity": "severe 8/10",
        },
        asked_questions=["What is the primary joint or muscle area causing you discomfort?"],
        chief_complaint="lower back pain",
        history_of_present_illness=HistoryOfPresentIllness(
            duration="2 weeks", severity="severe 8/10"
        ),
    )

    next_q = select_next_question(dummy_session)
    assert next_q is not None
    assert next_q["concept_key"] not in ("site", "duration", "severity")


# =========================================================================
# TEST I: Null/empty LLM extraction fallback and needs_review
# =========================================================================
def test_i_null_empty_llm_extraction_fallback_and_needs_review(client):
    sid = _start_adaptive_session(client, complaint="joint pain")

    # Mock extract_field returning null/empty extraction
    null_llm_resp = {"complaint": None, "confidence": 0.2, "concepts": {}}
    with patch.object(session_router, "extract_field", return_value=null_llm_resp):
        res = client.post(f"/session/{sid}/answer", json={"answer": "pain in my right shoulder"})
        assert res.status_code == 200
        body = res.json()
        assert body["needs_review"] is True
        # Interview still advances
        assert body["interview_status"] in ("in_progress", "complete")

    sess = client.get(f"/session/{sid}").json()
    assert sess["answer_records"][-1]["needs_review"] is True
    # Verbatim answer preserved
    assert sess["raw_answers"][-1]["answer"] == "pain in my right shoulder"
    assert sess["chief_complaint"] == "pain in my right shoulder"


# =========================================================================
# TEST J: Complete LLM failure advances without stalling
# =========================================================================
def test_j_complete_llm_failure_advances_without_stalling(client):
    sid = _start_adaptive_session(client, complaint="stomach burn")

    # LLM throws exception
    with patch.object(session_router, "extract_field", side_effect=RuntimeError("LLM API crashed")):
        res = client.post(f"/session/{sid}/answer", json={"answer": "burning sensation after eating"})
        assert res.status_code == 200
        body = res.json()
        assert body["needs_review"] is True
        assert body["red_flag"] is False

    sess = client.get(f"/session/{sid}").json()
    assert sess["raw_answers"][-1]["answer"] == "burning sensation after eating"
    assert len(sess["answer_records"]) == 1
    assert sess["answer_records"][0]["needs_review"] is True


# =========================================================================
# TEST K: Safety flag aborts adaptive questioning immediately
# =========================================================================
def test_k_safety_flag_aborts_adaptive_questioning_immediately(client):
    sid = _start_adaptive_session(client)

    # Red flag input
    res = client.post(f"/session/{sid}/answer", json={
        "answer": "I have crushing chest pain radiating to my left arm and sweating"
    })
    assert res.status_code == 200
    body = res.json()
    assert body["red_flag"] is True
    assert body["next_question"] is None
    assert body["interview_status"] == "safety_flagged"

    sess = client.get(f"/session/{sid}").json()
    assert sess["safety_flagged"] is True
    assert sess["next_question"] is None
    assert sess["interview_status"] == "safety_flagged"


# =========================================================================
# TEST L: Hard question cap enforced
# =========================================================================
def test_l_hard_question_cap_enforced(client):
    sid = _start_adaptive_session(client)

    # Feed answers one by one with minimal info
    mock_extract = lambda ans, current_concept=None, domain_hint=None: {
        "domain": "musculoskeletal",
        "concepts": {current_concept or "primary_symptom": ans},
        "confidence": 0.9,
    }

    with patch.object(session_router, "extract_field", side_effect=mock_extract):
        for i in range(MAX_ADAPTIVE_QUESTIONS):
            r = client.post(f"/session/{sid}/answer", json={"answer": f"Answer step {i}"})
            assert r.status_code == 200

    sess = client.get(f"/session/{sid}").json()
    assert sess["adaptive_question_count"] <= MAX_ADAPTIVE_QUESTIONS
    assert sess["interview_complete"] is True
    assert sess["next_question"] is None


# =========================================================================
# TEST M: Never repeats already-asked question
# =========================================================================
def test_m_never_repeats_already_asked_question():
    profile = get_presentation_profile(DOMAIN_MUSCULOSKELETAL)
    all_q_texts = [q.question_text for q in profile.question_sequence]

    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_MUSCULOSKELETAL,
        adaptive_question_count=3,
        collected_concepts={"primary_symptom": "knee pain"},
        asked_questions=all_q_texts[:3],
        chief_complaint="knee pain",
        history_of_present_illness=HistoryOfPresentIllness(),
    )

    next_q = select_next_question(dummy_session)
    if next_q:
        assert next_q["question_text"] not in dummy_session.asked_questions


# =========================================================================
# TEST N: Stop condition terminates cleanly
# =========================================================================
def test_n_stop_condition_terminates_cleanly():
    # When all required concepts are present and min concepts met
    profile = get_presentation_profile(DOMAIN_MUSCULOSKELETAL)
    dummy_session = SimpleNamespace(
        interview_complete=False,
        presentation_domain=DOMAIN_MUSCULOSKELETAL,
        adaptive_question_count=3,
        collected_concepts={
            "primary_symptom": "knee pain",
            "site": "right knee",
            "duration": "1 month",
            "aggravating_factors": "walking",
        },
        asked_questions=["Q1", "Q2", "Q3"],
        chief_complaint="knee pain",
        history_of_present_illness=HistoryOfPresentIllness(
            duration="1 month", character="right knee"
        ),
    )

    is_sufficient = evaluate_sufficiency(dummy_session)
    assert is_sufficient is True


# =========================================================================
# TEST O: Legacy session data upgrades cleanly
# =========================================================================
def test_o_legacy_session_data_upgrades_cleanly():
    # Session created without any adaptive fields
    legacy_session = Session(
        session_id="legacy-test-123",
        patient=Patient(name="Legacy Patient", age=60, gender="male"),
        language="en",
        visit_type="new",
        consent_given=True,
        patient_code="1234",
        interview_step="chief_complaint",
        interview_complete=False,
        chief_complaint=None,
        history_of_present_illness=HistoryOfPresentIllness(),
        documents=[],
        doctor_review=DoctorReview(),
        answer_records=[],
        raw_answers=[],
    )

    assert legacy_session.presentation_domain is None
    assert legacy_session.collected_concepts == {}
    assert legacy_session.asked_questions == []
    assert legacy_session.adaptive_question_count == 0
    assert legacy_session.adaptive is False

    # Bridge concepts to legacy
    legacy_session.collected_concepts = {
        "primary_symptom": "Severe back pain",
        "duration": "5 days",
        "severity": "moderate",
        "character": "dull ache",
        "associated_symptoms": ["stiffness", "mild fever"],
    }
    bridge_concepts_to_legacy(legacy_session)

    assert legacy_session.chief_complaint == "Severe back pain"
    assert legacy_session.history_of_present_illness.duration == "5 days"
    assert legacy_session.history_of_present_illness.severity == "moderate"
    assert legacy_session.history_of_present_illness.character == "dull ache"
    assert "stiffness" in legacy_session.history_of_present_illness.associated_symptoms
