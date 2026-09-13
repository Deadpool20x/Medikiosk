"""backend/tests/test_adaptive_interview.py.

LLM-as-Conversational-Interviewer contract tests (18 test points, §23).

The LLM proposes the next natural follow-up question; deterministic policy
validation (`validate_llm_proposal`) accepts, revises, or falls back. These
tests mock `session_router.generate_adaptive_turn` at the router boundary,
plus provider-level unit tests for the fallback chain.

End-to-end multi-turn conversation simulations and the Critical Acceptance
scenarios A-D live in `test_conversation_simulations.py`.
"""

import json
import os
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
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    MAX_ADAPTIVE_QUESTIONS,
    build_conversation_context,
    classify_presentation_domain,
    validate_llm_proposal,
)
from backend.services.llm_provider import generate_adaptive_turn


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_adaptive.db")
        os.environ["DATABASE_PATH"] = db_file
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start(client: TestClient, lang: str = "en", name: str = "Test Patient", age: int = 40, gender: str = "female") -> str:
    res = client.post(
        "/session/start",
        json={
            "patient": {"name": name, "age": age, "gender": gender},
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


def _proposal(
    domain: str,
    concepts: dict,
    q_text: str,
    q_concept: str,
    status: str = "continue",
    q_reason: str = "explore the concept",
    confidence: float = 0.9,
) -> dict:
    return {
        "case_update": {
            "presentation": domain,
            "concepts": concepts,
            "mentioned_documents": [],
        },
        "next_question": (
            {
                "text": q_text,
                "target_concept": q_concept,
                "reason": q_reason,
                "priority": "normal",
            }
            if q_text
            else None
        ),
        "status": status,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# 1-3. LLM drives direct domain-appropriate follow-up
# ---------------------------------------------------------------------------

def test_01_knee_answer_drives_musculoskeletal_follow_up(client):
    sid = _start(client)
    data = _answer(
        client, sid,
        "I twisted my right knee playing badminton yesterday and now it hurts badly.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "knee pain", "site": "right knee", "onset": "yesterday"},
            "Are you able to bear weight on the right leg, or does it feel unstable?",
            "functional_limitation",
        ),
    )
    assert data["next_question"] == "Are you able to bear weight on the right leg, or does it feel unstable?"
    assert data["presentation_domain"] == DOMAIN_MUSCULOSKELETAL
    assert data["needs_review"] is False
    assert data["session_complete"] is False


def test_02_dry_cough_answer_drives_respiratory_follow_up(client):
    sid = _start(client)
    data = _answer(
        client, sid,
        "I have had a dry hacking cough for 3 weeks, worse at night and in cold air.",
        _proposal(
            DOMAIN_RESPIRATORY,
            {"primary_symptom": "dry hacking cough", "duration": "3 weeks", "cough_character": "dry hacking"},
            "Do you feel any throat tickle or difficulty catching your breath during cough spasms?",
            "severity",
        ),
    )
    assert data["next_question"] == "Do you feel any throat tickle or difficulty catching your breath during cough spasms?"
    assert data["presentation_domain"] == DOMAIN_RESPIRATORY
    assert data["needs_review"] is False


def test_03_stomach_burning_answer_drives_digestive_follow_up(client):
    sid = _start(client)
    data = _answer(
        client, sid,
        "I have a burning sensation in my stomach after meals and irregular bowel habits recently.",
        _proposal(
            DOMAIN_DIGESTIVE,
            {"primary_symptom": "burning in stomach", "duration": "after meals", "bowel_habits": "irregular"},
            "Do you also feel bloated, nauseous, or have sour burping after meals?",
            "associated_symptoms",
        ),
    )
    assert data["next_question"] == "Do you also feel bloated, nauseous, or have sour burping after meals?"
    assert data["presentation_domain"] == DOMAIN_DIGESTIVE
    assert data["needs_review"] is False


# ---------------------------------------------------------------------------
# 4. No repeat of previously provided information
# ---------------------------------------------------------------------------

def test_04_validator_never_re_asks_information_the_patient_provided(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "The pain in my right knee is worse when I climb stairs.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "knee pain", "site": "right knee", "aggravating_factors": "worse climbing stairs"},
            "How long has this knee pain been present?",
            "duration",
        ),
    )
    assert first["needs_review"] is False

    second = _answer(
        client, sid,
        "About a week now, only when climbing.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"duration": "about a week"},
            "You said stairs make it worse, is that still the main trigger?",  # re-asks aggravating_factors
            "aggravating_factors",
        ),
    )
    assert second["needs_review"] is True
    assert second["next_question"] != "You said stairs make it worse, is that still the main trigger?"
    assert second["session_complete"] is False


# ---------------------------------------------------------------------------
# 5-7. Validator rejects invalid proposals (unit-level)
# ---------------------------------------------------------------------------

def _dummy_session(domain: str = DOMAIN_MUSCULOSKELETAL, collected=None, asked=None, count: int = 0):
    return SimpleNamespace(
        presentation_domain=domain,
        collected_concepts=collected or {},
        asked_concepts=asked or [],
        asked_questions=[],
        adaptive_question_count=count,
    )


def _proposal_namespace(concepts: dict, q_text: str | None, q_concept: str, status: str = "continue"):
    return SimpleNamespace(
        case_update=SimpleNamespace(concepts=concepts),
        next_question=SimpleNamespace(text=q_text, target_concept=q_concept, reason="r", priority="normal")
        if q_text
        else None,
        status=status,
    )


def test_05_validator_rejects_irrelevant_off_topic_question():
    result = validate_llm_proposal(
        _proposal_namespace({}, "What color is your shirt today?", "unrelated_thing"),
        _dummy_session(),
    )
    assert result.valid is False
    assert any("not in allowed concepts" in r for r in result.reasons)


def test_06_validator_rejects_diagnosis_treatment_question():
    result = validate_llm_proposal(
        _proposal_namespace({}, "You should take ibuprofen for this pain", "related_query"),
        _dummy_session(),
    )
    assert result.valid is False
    assert any("clinical scope ban" in r for r in result.reasons)


def test_07_validator_rejects_unsafe_medical_instruction():
    result = validate_llm_proposal(
        _proposal_namespace({}, "Do not go to the hospital for this problem", "related_query"),
        _dummy_session(),
    )
    assert result.valid is False
    assert any("clinical scope ban" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 8-9. LLM "sufficient" is honored only when deterministic sufficiency passes
# ---------------------------------------------------------------------------

def test_08_llm_sufficient_honored_when_mandatory_concepts_present(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "Pain in the left shoulder for the last two days.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "shoulder pain", "site": "left shoulder", "duration": "2 days"},
            "Does the pain also occur at rest, or only with movement?",
            "aggravating_factors",
        ),
    )
    assert first["session_complete"] is False

    second = _answer(
        client, sid,
        "Only when I move, otherwise fine.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"aggravating_factors": "only with movement"},
            None,
            "",
            status="sufficient",
            confidence=0.95,
        ),
    )
    assert second["session_complete"] is True
    assert second["next_question"] is None
    assert second["needs_review"] is False


def test_09_llm_sufficient_with_missing_mandatory_concept_keeps_intaking(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "Pain in my left knee.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "knee pain", "site": "left knee"},
            "How severe is the pain on a scale from 1 to 10?",
            "severity",
        ),
    )
    assert first["session_complete"] is False

    # Duration (mandatory for musculoskeletal) was never provided; must continue.
    second = _answer(
        client, sid,
        "About 7 out of 10.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"severity": "7/10"},
            None,
            "",
            status="sufficient",
            confidence=0.95,
        ),
    )
    assert second["session_complete"] is False
    assert second["next_question"] == "How long have you been experiencing this pain or stiffness?"
    assert second["needs_review"] is True


# ---------------------------------------------------------------------------
# 10-11. Provider fallback chain: primary -> fallback -> deterministic
# ---------------------------------------------------------------------------

async def test_10_primary_provider_failure_falls_back_to_second_provider():
    class FailingProvider:
        provider_name = "failing"

        async def generate(self, *a, **kw):
            raise RuntimeError("primary down")

    class WorkingProvider:
        provider_name = "working"

        async def generate(self, *a, **kw):
            return json.dumps({
                "case_update": {"presentation": DOMAIN_MUSCULOSKELETAL, "concepts": {"site": "knee"}, "mentioned_documents": []},
                "next_question": {"text": "Can you bend the knee fully?", "target_concept": "functional_limitation", "reason": "r", "priority": "normal"},
                "status": "continue",
                "confidence": 0.9,
            })

    context = {"language": "en", "current_answer": "my knee hurts", "collected_concepts": {}}
    result = await generate_adaptive_turn(context, providers=[FailingProvider(), WorkingProvider()])
    assert result["provider"] == "working"
    assert result["next_question"]["text"] == "Can you bend the knee fully?"


def test_11_all_providers_fail_falls_back_to_deterministic_question(client):
    sid = _start(client)
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(side_effect=RuntimeError("all down"))):
        with patch.object(session_router, "extract_case", AsyncMock(side_effect=RuntimeError("no providers"))):
            resp = client.post(f"/session/{sid}/answer", json={"answer": "right knee pain after a fall"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_review"] is True
    assert data["next_question"] is not None
    assert isinstance(data["next_question"], str) and len(data["next_question"]) > 5
    assert data["session_complete"] is False


# ---------------------------------------------------------------------------
# 12-13. Different inputs produce different trajectories
# ---------------------------------------------------------------------------

def test_12_same_patient_different_answer_produces_different_question(client):
    sid_a = _start(client, name="Patient X", age=35)
    data_a = _answer(
        client, sid_a,
        "I landed badly and my ankle swelled up.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "ankle pain", "site": "ankle", "stiffness_or_swelling": "swollen"},
            "Can you put weight on that ankle?", "functional_limitation",
        ),
    )

    sid_b = _start(client, name="Patient X", age=35)
    data_b = _answer(
        client, sid_b,
        "I have a dry cough that is worse at night.",
        _proposal(
            DOMAIN_RESPIRATORY,
            {"primary_symptom": "dry cough", "cough_character": "dry"},
            "Is the cough dry throughout, or does phlegm come up sometimes?", "severity",
        ),
    )

    assert data_a["next_question"] != data_b["next_question"]
    assert data_a["presentation_domain"] != data_b["presentation_domain"]


def test_13_different_patients_follow_different_paths(client):
    sid_a = _start(client, name="Patient A", age=28)
    seq_a = []
    seq_a.append(_answer(
        client, sid_a, "Knee pain after a ski fall.",
        _proposal(DOMAIN_MUSCULOSKELETAL, {"primary_symptom": "knee pain"},
                  "Does the knee feel stiff in the morning?", "stiffness_or_swelling"),
    ))
    seq_a.append(_answer(
        client, sid_a, "Yes, stiff and swollen.",
        _proposal(DOMAIN_MUSCULOSKELETAL, {"stiffness_or_swelling": "stiff and swollen"},
                  "Can you fully straighten the leg?", "functional_limitation"),
    ))

    sid_b = _start(client, name="Patient B", age=52)
    seq_b = []
    seq_b.append(_answer(
        client, sid_b, "Burning chest after meals.",
        _proposal(DOMAIN_DIGESTIVE, {"primary_symptom": "burning chest"},
                  "Does it also happen when you lie down at night?", "bowel_habits"),
    ))
    seq_b.append(_answer(
        client, sid_b, "Only after fried food.",
        _proposal(DOMAIN_DIGESTIVE, {"food_relationship": "after fried food"},
                  "How often does the burning trouble you in a week?", "duration"),
    ))

    qa = [d["next_question"] for d in seq_a]
    qb = [d["next_question"] for d in seq_b]
    assert qa != qb
    assert not set(qa) & set(qb)


# ---------------------------------------------------------------------------
# 14-15. Language-aware questions (Hindi / Gujarati)
# ---------------------------------------------------------------------------

def test_14_hindi_language_used_in_seeded_and_llm_questions(client):
    sid = _start(client, lang="hi")

    sess = client.get(f"/session/{sid}").json()
    assert sess["next_question"] == "आज क्लिनिक आने का आपका मुख्य कारण क्या है?"

    data = _answer(
        client, sid,
        "मेरे घुटने में दर्द है।",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "घुटने का दर्द", "site": "घुटना"},
            "क्या आप घुटने पर वज़न डाल सकते हैं, या वह अस्थिर लगता है?",
            "functional_limitation",
        ),
    )
    assert data["next_question"] == "क्या आप घुटने पर वज़न डाल सकते हैं, या वह अस्थिर लगता है?"


def test_15_gujarati_language_used_in_seeded_and_llm_questions(client):
    sid = _start(client, lang="gu")

    sess = client.get(f"/session/{sid}").json()
    assert sess["next_question"] == "આજે દવાખાને આવવાનું તમારું મુખ્ય કારણ શું છે?"

    data = _answer(
        client, sid,
        "મારા ઘૂંટણમાં દુખાવો છે.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "ઘૂંટણનો દુખાવો", "site": "ઘૂંટણ"},
            "શું તમે ઘૂંટણ પર વજન મૂકી શકો છો, કે તે અસ્થિર લાગે છે?",
            "functional_limitation",
        ),
    )
    assert data["next_question"] == "શું તમે ઘૂંટણ પર વજન મૂકી શકો છો, કે તે અસ્થિર લાગે છે?"


# ---------------------------------------------------------------------------
# 16. Hard turn limit enforced
# ---------------------------------------------------------------------------

def test_16_hard_max_turn_limit_is_enforced(client):
    sid = _start(client)
    targets = ["duration", "severity", "onset", "character", "associated_symptoms"]
    for idx, target in enumerate(targets):
        data = _answer(
            client, sid,
            f"answer number {idx + 1}",
            _proposal(DOMAIN_MUSCULOSKELETAL, {},
                      f"Please tell us more about {target}?",
                      target),
        )
    assert data["next_question"] is None  # 5th turn completes at hard cap
    assert data["session_complete"] is True

    resp = client.post(f"/session/{sid}/answer", json={"answer": "one more answer"})
    assert resp.status_code == 200
    after = resp.json()
    assert after["session_complete"] is True
    assert after["next_question"] is None
    sess = client.get(f"/session/{sid}").json()
    assert sess["adaptive_question_count"] == MAX_ADAPTIVE_QUESTIONS


# ---------------------------------------------------------------------------
# 17. Semantic repetition rejected (same concept, different wording)
# ---------------------------------------------------------------------------

def test_17_semantically_repetitive_question_is_rejected(client):
    sid = _start(client)
    first = _answer(
        client, sid,
        "Right knee pain.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"primary_symptom": "right knee pain"},
            "Are you able to walk on the right leg normally?",
            "functional_limitation",
        ),
    )
    assert first["needs_review"] is False

    # Same target_concept again, re-worded: must be rejected as repetition.
    second = _answer(
        client, sid,
        "No, I limp a little.",
        _proposal(
            DOMAIN_MUSCULOSKELETAL,
            {"functional_limitation": "limps slightly"},
            "How well can you move around on that leg day to day?",
            "functional_limitation",
        ),
    )
    assert second["needs_review"] is True
    assert second["next_question"] != "How well can you move around on that leg day to day?"


# ---------------------------------------------------------------------------
# 18. Critical Acceptance A-D: four presentations diverge into four domains
#       Full end-to-end question trajectories are exercised in
#       test_conversation_simulations.py::test_critical_acceptance_scenarios_a_b_c_d
# ---------------------------------------------------------------------------

def test_18_critical_acceptance_scenarios_classify_into_four_distinct_domains():
    scenario_a = "I missed a step on the stairs 2 days ago and twisted my right knee. It is swollen."
    scenario_b = "I have had a dry hacking cough for 3 weeks, worse at night and in cold air."
    scenario_c = "I have a burning sensation in my stomach and irregular bowel habits recently."
    scenario_d = "I just feel weak and tired all the time, I cannot say why."

    domains = [
        classify_presentation_domain(scenario_a),
        classify_presentation_domain(scenario_b),
        classify_presentation_domain(scenario_c),
        classify_presentation_domain(scenario_d),
    ]

    assert domains[0] == DOMAIN_MUSCULOSKELETAL
    assert domains[1] == DOMAIN_RESPIRATORY
    assert domains[2] == DOMAIN_DIGESTIVE
    assert domains[3] == DOMAIN_GENERAL
    assert len(set(domains)) == 4


# ---------------------------------------------------------------------------
# Bounded context: the LLM sees a fixed, bounded conversational window
# ---------------------------------------------------------------------------

def test_bounded_context_caps_history_and_carries_language():
    s = SimpleNamespace(
        session_id="test",
        language="gu",
        patient=SimpleNamespace(name="Test", age=40, gender="female"),
        raw_answers=[{"field": "primary_symptom", "question_text": "q", "answer": "a"}] * 8,
        asked_questions=["q"] * 8,
        asked_concepts=["primary_symptom"] * 8,
        collected_concepts={"primary_symptom": "a"},
        presentation_domain=None,
        chief_complaint="stomach pain",
        adaptive_question_count=8,
    )

    ctx = build_conversation_context(s, "my answer")
    assert len(ctx["conversation_history"]) <= 5
    assert ctx["language"] == "gu"
    assert ctx["turn_count"] == 8
    assert ctx["max_turns"] == MAX_ADAPTIVE_QUESTIONS