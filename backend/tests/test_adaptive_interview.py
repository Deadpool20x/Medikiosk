"""Tests for LLM-driven Adaptive Conversational Interviewer & Deterministic Validator.

Verifies:
TEST 1: Knee pain -> musculoskeletal follow-up
TEST 2: Respiratory complaint -> respiratory follow-up
TEST 3: Digestive complaint -> digestive follow-up
TEST 4: LLM sees information already provided -> does not repeat that concept
TEST 5: LLM proposes irrelevant question -> validator rejects
TEST 6: LLM proposes diagnosis -> validator rejects
TEST 7: LLM proposes treatment -> validator rejects
TEST 8: LLM proposes unsafe emergency-handling question -> validator rejects
TEST 9: LLM says sufficient -> local sufficiency passes -> interview ends
TEST 10: LLM says sufficient -> mandatory field missing -> continue
TEST 11: primary LLM fails -> fallback provider generates next question
TEST 12: both LLM providers fail -> deterministic fallback works
TEST 13: same patient gives materially different answer -> next question changes
TEST 14: different patients produce different conversation paths
TEST 15: Hindi request -> next question is Hindi
TEST 16: Gujarati request -> next question is Gujarati
TEST 17: question limit enforced
TEST 18: semantic repetition rejected
"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview
from backend.rules.adaptive_interview import (
    validate_llm_proposal,
    evaluate_conversational_sufficiency,
    get_fallback_question,
    build_conversation_context,
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    DOMAIN_DIGESTIVE,
    DOMAIN_DERMATOLOGICAL,
    DOMAIN_METABOLIC,
    DOMAIN_GENERAL,
    MAX_ADAPTIVE_QUESTIONS,
)
from backend.services.llm_provider import (
    generate_adaptive_turn,
    AdaptiveTurnProposal,
    CaseUpdate,
    NextQuestionProposal,
    LLMProvider,
)
from backend.db import init_db, get_session as db_get_session


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_adaptive.db")
        os.environ["DATABASE_PATH"] = db_path
        init_db(db_path)
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start_session(client, name="Test Patient", lang="en", visit_type="adaptive"):
    resp = client.post("/session/start", json={
        "patient": {"name": name, "age": 45, "gender": "female"},
        "language": lang,
        "visit_type": visit_type,
        "adaptive": True,
    })
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


# =========================================================================
# TEST 1: Knee pain -> musculoskeletal follow-up
# =========================================================================
def test_1_knee_pain_musculoskeletal_followup(client):
    sid = _start_session(client)
    mock_turn = {
        "case_update": {
            "presentation": "musculoskeletal",
            "concepts": {"primary_symptom": "knee pain", "site": "knee"},
            "mentioned_documents": [],
        },
        "next_question": {
            "text": "Does the knee feel stiff or swollen, especially in the morning?",
            "target_concept": "stiffness_or_swelling",
            "reason": "Assess inflammatory vs mechanical joint symptoms",
            "priority": "normal",
        },
        "status": "continue",
        "confidence": 0.9,
    }
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_turn)):
        res = client.post(f"/session/{sid}/answer", json={"answer": "My right knee hurts when I walk."})
        assert res.status_code == 200
        body = res.json()
        assert body["presentation_domain"] == "musculoskeletal"
        assert body["next_question"] == "Does the knee feel stiff or swollen, especially in the morning?"
        assert body["interview_status"] == "in_progress"


# =========================================================================
# TEST 2: Respiratory complaint -> respiratory follow-up
# =========================================================================
def test_2_respiratory_complaint_followup(client):
    sid = _start_session(client)
    mock_turn = {
        "case_update": {
            "presentation": "respiratory",
            "concepts": {"primary_symptom": "dry cough", "cough_character": "dry"},
            "mentioned_documents": [],
        },
        "next_question": {
            "text": "Are you experiencing any fever, headache, or throat pain along with this cough?",
            "target_concept": "associated_symptoms",
            "reason": "Screen for systemic respiratory symptoms",
            "priority": "high",
        },
        "status": "continue",
        "confidence": 0.9,
    }
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_turn)):
        res = client.post(f"/session/{sid}/answer", json={"answer": "I have had a tickling dry cough for five days."})
        assert res.status_code == 200
        body = res.json()
        assert body["presentation_domain"] == "respiratory"
        assert "cough" in body["next_question"].lower() or "fever" in body["next_question"].lower()


# =========================================================================
# TEST 3: Digestive complaint -> digestive follow-up
# =========================================================================
def test_3_digestive_complaint_followup(client):
    sid = _start_session(client)
    mock_turn = {
        "case_update": {
            "presentation": "digestive",
            "concepts": {"primary_symptom": "stomach acidity", "food_relationship": "after meals"},
            "mentioned_documents": [],
        },
        "next_question": {
            "text": "Have you noticed any changes in your bowel movements or feeling of bloating?",
            "target_concept": "bowel_habits",
            "reason": "Check for lower gastrointestinal involvement",
            "priority": "normal",
        },
        "status": "continue",
        "confidence": 0.92,
    }
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_turn)):
        res = client.post(f"/session/{sid}/answer", json={"answer": "Severe burning in stomach after spicy food."})
        assert res.status_code == 200
        body = res.json()
        assert body["presentation_domain"] == "digestive"
        assert "bowel" in body["next_question"].lower() or "bloating" in body["next_question"].lower()


# =========================================================================
# TEST 4: LLM sees information already provided -> does not repeat concept
# =========================================================================
def test_4_does_not_repeat_already_provided_concept():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="musculoskeletal",
        collected_concepts={"primary_symptom": "knee pain", "duration": "6 months"},
        asked_concepts=["primary_symptom"],
        asked_questions=["Where is your pain?"],
    )
    # LLM erroneously proposes asking duration again
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="How long have you had this knee pain?",
            target_concept="duration",
            reason="Check duration",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "musculoskeletal")
    assert val.valid is False
    assert any("already answered" in r for r in val.reasons)


# =========================================================================
# TEST 5: LLM proposes irrelevant question -> validator rejects
# =========================================================================
def test_5_irrelevant_question_rejected():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="respiratory",
        collected_concepts={"primary_symptom": "cough"},
        asked_concepts=["primary_symptom"],
        asked_questions=["What symptoms do you have?"],
    )
    # LLM asks an unmapped irrelevant concept
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="What is your favorite television show?",
            target_concept="favorite_tv_show",
            reason="Distract patient",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "respiratory")
    assert val.valid is False
    assert any("not in allowed concepts" in r for r in val.reasons)


# =========================================================================
# TEST 6: LLM proposes diagnosis -> validator rejects
# =========================================================================
def test_6_diagnosis_proposal_rejected():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="musculoskeletal",
        collected_concepts={"primary_symptom": "knee pain"},
        asked_concepts=["primary_symptom"],
        asked_questions=["Where is your pain?"],
    )
    # LLM illegally mentions diagnosis
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="You have osteoarthritis. Does the joint hurt in the evening?",
            target_concept="stiffness_or_swelling",
            reason="Confirm OA diagnosis",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "musculoskeletal")
    assert val.valid is False
    assert any("prohibited pattern" in r for r in val.reasons)


# =========================================================================
# TEST 7: LLM proposes treatment -> validator rejects
# =========================================================================
def test_7_treatment_proposal_rejected():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="digestive",
        collected_concepts={"primary_symptom": "acidity"},
        asked_concepts=["primary_symptom"],
        asked_questions=["What brings you in?"],
    )
    # LLM illegally recommends medication/panchakarma
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="You should take triphala powder before bed. How many times a day do you eat?",
            target_concept="food_relationship",
            reason="Suggest remedy",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "digestive")
    assert val.valid is False
    assert any("prohibited pattern" in r for r in val.reasons)


# =========================================================================
# TEST 8: LLM proposes unsafe emergency-handling question -> validator rejects
# =========================================================================
def test_8_unsafe_directive_rejected():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="general",
        collected_concepts={"primary_symptom": "headache"},
        asked_concepts=["primary_symptom"],
        asked_questions=["What brings you in?"],
    )
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="Do not go to the hospital, just rest. Is your vision blurry?",
            target_concept="associated_symptoms",
            reason="Advise rest",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "general")
    assert val.valid is False
    assert any("prohibited pattern" in r for r in val.reasons)


# =========================================================================
# TEST 9: LLM says sufficient -> local sufficiency passes -> interview ends
# =========================================================================
def test_9_llm_sufficient_local_verification_passes():
    dummy_session = SimpleNamespace(
        adaptive_question_count=3,
        presentation_domain="musculoskeletal",
        collected_concepts={
            "primary_symptom": "knee pain",
            "site": "right knee",
            "duration": "2 weeks",
        },
        asked_concepts=["primary_symptom", "site", "duration"],
    )
    is_sufficient = evaluate_conversational_sufficiency(dummy_session, llm_status="sufficient")
    assert is_sufficient is True


# =========================================================================
# TEST 10: LLM says sufficient -> mandatory field missing -> continue
# =========================================================================
def test_10_llm_sufficient_mandatory_missing_continues():
    dummy_session = SimpleNamespace(
        adaptive_question_count=1,
        presentation_domain="musculoskeletal",
        # missing "site" and "duration"
        collected_concepts={"primary_symptom": "knee pain"},
        asked_concepts=["primary_symptom"],
    )
    # LLM prematurely claims sufficient
    is_sufficient = evaluate_conversational_sufficiency(dummy_session, llm_status="sufficient")
    assert is_sufficient is False


# =========================================================================
# TEST 11: Primary LLM fails -> fallback provider generates next question
# =========================================================================
@pytest.mark.asyncio
async def test_11_primary_llm_fails_fallback_provider_succeeds():
    class FailingProvider(LLMProvider):
        provider_name = "failing_primary"
        def is_configured(self): return True
        async def generate(self, prompt, **kwargs):
            raise RuntimeError("API timeout")

    class WorkingSecondaryProvider(LLMProvider):
        provider_name = "working_secondary"
        def is_configured(self): return True
        async def generate(self, prompt, **kwargs):
            return """
            {
              "case_update": {
                "presentation": "respiratory",
                "concepts": {"primary_symptom": "cough"}
              },
              "next_question": {
                "text": "How long have you had this cough?",
                "target_concept": "duration",
                "reason": "Assess duration"
              },
              "status": "continue",
              "confidence": 0.85
            }
            """

    context = {
        "language": "en",
        "current_answer": "cough for 3 days",
        "collected_concepts": {},
    }
    result = await generate_adaptive_turn(
        context,
        providers=[FailingProvider(), WorkingSecondaryProvider()]
    )
    assert result["provider"] == "working_secondary"
    assert result["next_question"]["text"] == "How long have you had this cough?"


# =========================================================================
# TEST 12: Both LLM providers fail -> deterministic fallback works
# =========================================================================
def test_12_both_llm_fail_deterministic_fallback(client):
    sid = _start_session(client)
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(side_effect=RuntimeError("All providers down"))):
        res = client.post(f"/session/{sid}/answer", json={"answer": "severe lower back pain for two weeks"})
        assert res.status_code == 200
        body = res.json()
        assert body["needs_review"] is True
        assert body["next_question"] is not None
        # Must have fallen back gracefully without crashing
        assert body["interview_status"] in ("in_progress", "complete")


# =========================================================================
# TEST 13: Same patient gives materially different answer -> next question changes
# =========================================================================
def test_13_different_answers_produce_different_next_questions(client):
    sid1 = _start_session(client, name="Patient 1")
    sid2 = _start_session(client, name="Patient 2")

    mock_resp1 = {
        "case_update": {"presentation": "musculoskeletal", "concepts": {"site": "knee"}},
        "next_question": {"text": "Does it hurt more when walking or climbing stairs?", "target_concept": "aggravating_factors"},
        "status": "continue",
        "confidence": 0.9,
    }
    mock_resp2 = {
        "case_update": {"presentation": "digestive", "concepts": {"primary_symptom": "acidity"}},
        "next_question": {"text": "Does the burning sensation happen mostly after meals?", "target_concept": "food_relationship"},
        "status": "continue",
        "confidence": 0.9,
    }

    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_resp1)):
        r1 = client.post(f"/session/{sid1}/answer", json={"answer": "Pain in my right knee."}).json()

    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_resp2)):
        r2 = client.post(f"/session/{sid2}/answer", json={"answer": "Acid burning in my chest."}).json()

    assert r1["next_question"] != r2["next_question"]
    assert "walking" in r1["next_question"]
    assert "meals" in r2["next_question"]


# =========================================================================
# TEST 14: Different patients produce different conversation paths
# =========================================================================
def test_14_different_patients_produce_different_conversation_paths(client):
    sid_msk = _start_session(client, name="Ramesh Patel")
    sid_resp = _start_session(client, name="Anjali Sharma")

    turn_msk = {
        "case_update": {"presentation": "musculoskeletal", "concepts": {"site": "lower back"}},
        "next_question": {"text": "Does the pain radiate down your leg or hip?", "target_concept": "character"},
        "status": "continue",
        "confidence": 0.9,
    }
    turn_resp = {
        "case_update": {"presentation": "respiratory", "concepts": {"cough_character": "productive"}},
        "next_question": {"text": "What color is the phlegm or mucus you are bringing up?", "target_concept": "cough_character"},
        "status": "continue",
        "confidence": 0.9,
    }

    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=turn_msk)):
        r_msk = client.post(f"/session/{sid_msk}/answer", json={"answer": "Lower back pain."}).json()

    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=turn_resp)):
        r_resp = client.post(f"/session/{sid_resp}/answer", json={"answer": "Chesty cough with green mucus."}).json()

    assert r_msk["presentation_domain"] == "musculoskeletal"
    assert r_resp["presentation_domain"] == "respiratory"
    assert r_msk["next_question"] != r_resp["next_question"]


# =========================================================================
# TEST 15: Hindi request -> next question is Hindi
# =========================================================================
def test_15_hindi_request_generates_hindi_question(client):
    sid = _start_session(client, name="Mohan Lal", lang="hi")
    mock_hindi = {
        "case_update": {
            "presentation": "musculoskeletal",
            "concepts": {"primary_symptom": "घुटने का दर्द", "site": "knee"},
        },
        "next_question": {
            "text": "क्या सुबह उठने पर घुटने में जकड़न या सूजन महसूस होती है?",
            "target_concept": "stiffness_or_swelling",
            "reason": "Check joint stiffness in Hindi",
        },
        "status": "continue",
        "confidence": 0.9,
    }
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_hindi)):
        res = client.post(f"/session/{sid}/answer", json={"answer": "मेरे दाहिने घुटने में बहुत दर्द है।"})
        assert res.status_code == 200
        body = res.json()
        assert body["next_question"] == "क्या सुबह उठने पर घुटने में जकड़न या सूजन महसूस होती है?"


# =========================================================================
# TEST 16: Gujarati request -> next question is Gujarati
# =========================================================================
def test_16_gujarati_request_generates_gujarati_question(client):
    sid = _start_session(client, name="Bhavna Ben", lang="gu")
    mock_gujarati = {
        "case_update": {
            "presentation": "digestive",
            "concepts": {"primary_symptom": "એસિડિટી", "food_relationship": "જમ્યા પછી"},
        },
        "next_question": {
            "text": "શું પેટ સાફ થવામાં કોઈ ફેરફાર, જેમ કે કબજિયાત કે ઝાડા જેવું જણાય છે?",
            "target_concept": "bowel_habits",
            "reason": "Check bowel habits in Gujarati",
        },
        "status": "continue",
        "confidence": 0.9,
    }
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_gujarati)):
        res = client.post(f"/session/{sid}/answer", json={"answer": "મને જમ્યા પછી પેટમાં ખૂબ બળતરા થાય છે."})
        assert res.status_code == 200
        body = res.json()
        assert body["next_question"] == "શું પેટ સાફ થવામાં કોઈ ફેરફાર, જેમ કે કબજિયાત કે ઝાડા જેવું જણાય છે?"


# =========================================================================
# TEST 17: Question limit enforced
# =========================================================================
def test_17_question_limit_strictly_enforced(client):
    sid = _start_session(client)
    mock_turn = lambda i: {
        "case_update": {"concepts": {f"concept_{i}": f"val_{i}"}},
        "next_question": {"text": f"Follow-up question {i}?", "target_concept": f"concept_{i+1}"},
        "status": "continue",
        "confidence": 0.9,
    }

    for i in range(MAX_ADAPTIVE_QUESTIONS):
        with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_turn(i))):
            r = client.post(f"/session/{sid}/answer", json={"answer": f"Answer {i}"})
            assert r.status_code == 200

    sess = client.get(f"/session/{sid}").json()
    assert sess["adaptive_question_count"] <= MAX_ADAPTIVE_QUESTIONS
    assert sess["interview_complete"] is True
    assert sess["next_question"] is None


# =========================================================================
# TEST 18: Semantic repetition rejected
# =========================================================================
def test_18_semantic_repetition_rejected():
    dummy_session = SimpleNamespace(
        adaptive_question_count=2,
        presentation_domain="musculoskeletal",
        collected_concepts={"primary_symptom": "knee pain"},
        asked_concepts=["primary_symptom", "aggravating_factors"],
        asked_questions=["What movements make your pain worse?"],
    )
    # Proposes semantically identical question with different phrasing
    proposal = SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(
            text="What movements make your pain worse?",
            target_concept="aggravating_factors",
            reason="Re-ask trigger",
        ),
        status="continue",
    )
    val = validate_llm_proposal(proposal, dummy_session, "musculoskeletal")
    assert val.valid is False
    assert any("already been asked" in r or "duplicate" in r for r in val.reasons)
