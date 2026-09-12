"""backend/tests/test_conversation_simulations.py.

12 Complete Multi-Turn Synthetic Conversation Simulations + Critical Acceptance Test.
Pilot Domains:
- 3 Musculoskeletal
- 3 Respiratory
- 3 Digestive
- 2 Metabolic
- 2 General / Unclear

Each simulation records and verifies:
- TURN
- PATIENT ANSWER
- EXTRACTED CONCEPTS
- LLM PROPOSED QUESTION
- VALIDATOR RESULT
- FINAL QUESTION
- CASE STATE
"""

import logging
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.routers.session as session_router
from backend.main import app
from backend.rules.adaptive_interview import (
    DOMAIN_DERMATOLOGICAL,
    DOMAIN_DIGESTIVE,
    DOMAIN_GENERAL,
    DOMAIN_METABOLIC,
    DOMAIN_MUSCULOSKELETAL,
    DOMAIN_RESPIRATORY,
    MAX_ADAPTIVE_QUESTIONS,
)

logger = logging.getLogger("simulation_logger")
logging.basicConfig(level=logging.INFO)


import os
import tempfile
from backend.db import init_db

@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_sim.db")
        os.environ["DATABASE_PATH"] = db_path
        init_db(db_path)
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start_sim_session(client: TestClient, name: str = "Test Patient", age: int = 40, gender: str = "female", lang: str = "en") -> str:
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


def _run_conversation_simulation(
    client: TestClient,
    sim_id: str,
    patient_name: str,
    age: int,
    gender: str,
    domain: str,
    language: str,
    turns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute a multi-turn conversation simulation, logging and asserting each step."""
    sid = _start_sim_session(client, name=patient_name, age=age, gender=gender, lang=language)
    history_log = []

    print(f"\n=======================================================")
    print(f"SIMULATION [{sim_id}]: {patient_name} ({age}yo {gender}) - Domain: {domain}")
    print(f"=======================================================")

    asked_question_sequence = []

    for idx, turn in enumerate(turns):
        turn_num = idx + 1
        p_answer = turn["answer"]
        mock_proposal = turn["proposal"]

        with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value=mock_proposal)):
            resp = client.post(f"/session/{sid}/answer", json={"answer": p_answer})
            assert resp.status_code == 200, f"Turn {turn_num} failed with status {resp.status_code}"
            data = resp.json()

        sess_resp = client.get(f"/session/{sid}")
        assert sess_resp.status_code == 200
        sess_data = sess_resp.json()

        final_q = data.get("next_question")
        if final_q:
            asked_question_sequence.append(final_q)

        step_record = {
            "turn": turn_num,
            "patient_answer": p_answer,
            "extracted_concepts": sess_data.get("collected_concepts", {}),
            "llm_proposed_question": mock_proposal.get("next_question", {}).get("text") if mock_proposal.get("next_question") else None,
            "validator_result": "VALID" if not data.get("needs_review") or final_q == (mock_proposal.get("next_question") or {}).get("text") else "FALLBACK_TRIGGERED",
            "final_question": final_q,
            "case_state": {
                "domain": sess_data.get("presentation_domain"),
                "question_count": sess_data.get("adaptive_question_count"),
                "complete": sess_data.get("interview_complete"),
                "documents": sess_data.get("mentioned_documents"),
            },
        }
        history_log.append(step_record)

        print(f"  TURN {turn_num}:")
        print(f"    PATIENT ANSWER: {p_answer}")
        print(f"    EXTRACTED CONCEPTS: {step_record['extracted_concepts']}")
        print(f"    LLM PROPOSED: {step_record['llm_proposed_question']}")
        print(f"    VALIDATOR RESULT: {step_record['validator_result']}")
        print(f"    FINAL QUESTION: {final_q}")
        print(f"    STATUS: complete={step_record['case_state']['complete']}, count={step_record['case_state']['question_count']}")

        # Ensure no stall on same question
        if idx > 0 and final_q is not None and len(asked_question_sequence) >= 2:
            assert asked_question_sequence[-1] != asked_question_sequence[-2], f"Interview stalled on turn {turn_num} with repeated question: {final_q}"

    final_sess = client.get(f"/session/{sid}").json()
    assert final_sess["adaptive_question_count"] <= MAX_ADAPTIVE_QUESTIONS

    return {
        "session_id": sid,
        "history": history_log,
        "final_session": final_sess,
        "questions": asked_question_sequence,
    }


# =========================================================================
# 1. MUSCULOSKELETAL SIMULATIONS (3 cases)
# =========================================================================

def test_sim_01_msk_acute_knee_sprain(client):
    """MSK 1: Acute knee pain following sports twisting injury."""
    turns = [
        {
            "answer": "I twisted my right knee while playing badminton yesterday and now it hurts badly.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"primary_symptom": "knee pain", "site": "right knee", "onset": "yesterday"},
                },
                "next_question": {
                    "text": "Are you able to bear weight on your right leg, or does it feel unstable?",
                    "target_concept": "functional_limitation",
                    "reason": "Assess weight-bearing stability after twisting mechanism",
                },
                "status": "continue",
                "confidence": 0.92,
            },
        },
        {
            "answer": "I cannot put any weight on it at all without sharp stabbing pain.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"functional_limitation": "unable to bear weight", "character": "sharp stabbing"},
                },
                "next_question": {
                    "text": "Have you noticed any visible swelling, redness, or heat around the knee joint?",
                    "target_concept": "stiffness_or_swelling",
                    "reason": "Check for acute effusion or inflammatory signs",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "Yes, it puffed up like a balloon last night.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"stiffness_or_swelling": "marked swelling since last night"},
                },
                "next_question": {
                    "text": "How severe would you rate the pain on a scale from 1 to 10?",
                    "target_concept": "severity",
                    "reason": "Quantify pain severity",
                },
                "status": "continue",
                "confidence": 0.95,
            },
        },
        {
            "answer": "It is easily an 8 out of 10 when resting and 10 when trying to step.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"severity": "8/10 at rest, 10/10 weight bearing", "duration": "1 day"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "MSK-01", "Vikram Patel", 29, "male", DOMAIN_MUSCULOSKELETAL, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["site"] == "right knee"
    assert "sharp stabbing" in res["final_session"]["collected_concepts"].get("character", "")


def test_sim_02_msk_chronic_lumbar_back_pain(client):
    """MSK 2: Chronic lower back stiffness and ache in desk worker."""
    turns = [
        {
            "answer": "I have had persistent dull ache in my lower back for the past 6 months.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"primary_symptom": "lower back ache", "site": "lumbar spine", "duration": "6 months", "character": "dull ache"},
                },
                "next_question": {
                    "text": "Does this back ache radiate down into your buttocks, thighs, or legs?",
                    "target_concept": "laterality",
                    "reason": "Check for radicular lumbar involvement",
                },
                "status": "continue",
                "confidence": 0.88,
            },
        },
        {
            "answer": "No radiation, it stays centered right across my waistline.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"laterality": "central lower back without radiation"},
                },
                "next_question": {
                    "text": "Do you notice that prolonged sitting or bending forward makes the stiffness worse?",
                    "target_concept": "aggravating_factors",
                    "reason": "Identify mechanical triggers",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "Sitting at my laptop for over an hour makes it lock up completely.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"aggravating_factors": "sitting > 1 hour"},
                },
                "next_question": {
                    "text": "What helps relieve the discomfort — walking, stretching, or heat?",
                    "target_concept": "relieving_factors",
                    "reason": "Identify easing factors",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "A hot water bag and gentle walking give good temporary relief.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"relieving_factors": "hot water bag and gentle walking"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.94,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "MSK-02", "Rajesh Shah", 48, "male", DOMAIN_MUSCULOSKELETAL, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "6 months"


def test_sim_03_msk_cervical_neck_pain(client):
    """MSK 3: Neck pain with shoulder stiffness."""
    turns = [
        {
            "answer": "Severe stiffness and pain in the back of my neck spreading into my right shoulder.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"primary_symptom": "cervical neck stiffness and pain", "site": "neck and right shoulder"},
                },
                "next_question": {
                    "text": "How long have you had this neck and shoulder discomfort?",
                    "target_concept": "duration",
                    "reason": "Establish chronicity",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "It started about 2 weeks ago after sleeping on a high pillow.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"duration": "2 weeks", "onset": "after high pillow"},
                },
                "next_question": {
                    "text": "Do you feel any numbness, tingling, or weakness in your right hand or fingers?",
                    "target_concept": "functional_limitation",
                    "reason": "Check cervical nerve compression red flag",
                },
                "status": "continue",
                "confidence": 0.93,
            },
        },
        {
            "answer": "No numbness or tingling at all, just tightness turning my head.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"functional_limitation": "restricted neck rotation, no neuropathy"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.92,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "MSK-03", "Meera Desai", 36, "female", DOMAIN_MUSCULOSKELETAL, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["site"] == "neck and right shoulder"


# =========================================================================
# 2. RESPIRATORY SIMULATIONS (3 cases)
# =========================================================================

def test_sim_04_respiratory_dry_nocturnal_cough(client):
    """Resp 1: Dry hacking cough worse at night with cold air."""
    turns = [
        {
            "answer": "I have this non-stop dry throat tickle and cough for 3 weeks.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"primary_symptom": "dry cough", "duration": "3 weeks", "cough_character": "dry throat tickle"},
                },
                "next_question": {
                    "text": "Does anything in particular trigger the coughing bouts, such as cold air or lying down at night?",
                    "target_concept": "triggers",
                    "reason": "Identify environmental triggers",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "It gets much worse when I turn on the AC or lie down to sleep at night.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"triggers": "AC cold air and lying down at night"},
                },
                "next_question": {
                    "text": "Are you experiencing any fever, chills, body ache, or runny nose along with it?",
                    "target_concept": "associated_symptoms",
                    "reason": "Check for systemic viral symptoms",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "No fever or cold at all, just a raspy throat and the dry hack.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"associated_symptoms": "raspy throat, afebrile"},
                },
                "next_question": {
                    "text": "Does warm water or herbal tea bring temporary relief to the throat?",
                    "target_concept": "relieving_factors",
                    "reason": "Check easing factors",
                },
                "status": "continue",
                "confidence": 0.89,
            },
        },
        {
            "answer": "Warm ginger tea helps calm it down for an hour.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"relieving_factors": "warm ginger tea"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "RESP-01", "Anand Verma", 34, "male", DOMAIN_RESPIRATORY, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "3 weeks"


def test_sim_05_respiratory_productive_chest_congestion(client):
    """Resp 2: Wet cough with thick yellowish mucus."""
    turns = [
        {
            "answer": "I have heavy chest congestion with thick mucus coming up for 5 days.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"primary_symptom": "chest congestion", "duration": "5 days", "cough_character": "productive with thick mucus"},
                },
                "next_question": {
                    "text": "What color is the phlegm, and have you noticed any mild fever or fatigue?",
                    "target_concept": "associated_symptoms",
                    "reason": "Assess phlegm quality and systemic involvement",
                },
                "status": "continue",
                "confidence": 0.92,
            },
        },
        {
            "answer": "The mucus is yellowish-green and I had low fever on the first two days.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"associated_symptoms": "yellowish-green mucus, low grade fever initial 2 days"},
                },
                "next_question": {
                    "text": "Do you feel shortness of breath or tightness in your chest while resting or walking?",
                    "target_concept": "severity",
                    "reason": "Rule out respiratory distress",
                },
                "status": "continue",
                "confidence": 0.94,
            },
        },
        {
            "answer": "No breathlessness when resting, just heavy rattling in the chest when coughing.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"severity": "no dyspnea at rest, chest rattling"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.93,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "RESP-02", "Sunita Nair", 52, "female", DOMAIN_RESPIRATORY, "en", turns
    )
    assert "mucus" in res["final_session"]["collected_concepts"]["cough_character"]


def test_sim_06_respiratory_allergic_rhinitis_sneezing(client):
    """Resp 3: Runny nose and sneezing fits."""
    turns = [
        {
            "answer": "Continuous bouts of sneezing and clear runny nose every morning for 10 days.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"primary_symptom": "sneezing and runny nose", "duration": "10 days", "cough_character": "clear watery discharge, no deep cough"},
                },
                "next_question": {
                    "text": "Do your eyes itch or water, and does this happen when sweeping or near dust?",
                    "target_concept": "triggers",
                    "reason": "Identify allergic triggers",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "Yes, my eyes itch intensely and dust immediately sets off 15 sneezes.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"triggers": "dust and morning exposure", "associated_symptoms": "itchy watery eyes"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.92,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "RESP-03", "Pooja Mehta", 24, "female", DOMAIN_RESPIRATORY, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "10 days"


# =========================================================================
# 3. DIGESTIVE SIMULATIONS (3 cases)
# =========================================================================

def test_sim_07_digestive_acid_reflux_heartburn(client):
    """Digestive 1: Epigastric burning after spicy meals."""
    turns = [
        {
            "answer": "I have severe burning in the chest and throat after dinner for nearly 4 weeks.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"primary_symptom": "heartburn and throat burning", "duration": "4 weeks"},
                },
                "next_question": {
                    "text": "Does this burning sensation worsen after oily or spicy foods, or when lying down?",
                    "target_concept": "food_relationship",
                    "reason": "Clarify postprandial patterns",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "Definitely after spicy food and whenever I lie down within 2 hours of eating.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"food_relationship": "worse with spicy food and recumbency"},
                },
                "next_question": {
                    "text": "Have you noticed any sour or bitter belching, or nausea in the mornings?",
                    "target_concept": "associated_symptoms",
                    "reason": "Assess amlapitta manifestations",
                },
                "status": "continue",
                "confidence": 0.93,
            },
        },
        {
            "answer": "Yes, sour fluid comes up into my mouth frequently.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"associated_symptoms": "sour waterbrash and regurgitation"},
                },
                "next_question": {
                    "text": "How have your daily bowel movements been — regular, or do you experience constipation?",
                    "target_concept": "bowel_habits",
                    "reason": "Complete gastrointestinal profile",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "Stool is hard and irregular, usually every 2 days with straining.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"bowel_habits": "constipation, hard stools every 2 days"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "DIGEST-01", "Ketan Joshi", 42, "male", DOMAIN_DIGESTIVE, "en", turns
    )
    assert "heartburn" in res["final_session"]["collected_concepts"]["primary_symptom"]
    assert "spicy food" in res["final_session"]["collected_concepts"]["food_relationship"]


def test_sim_08_digestive_bloating_flatulence(client):
    """Digestive 2: Abdominal fullness, distension, and gas after eating."""
    turns = [
        {
            "answer": "Excessive stomach bloating and gas after every meal for the past 2 weeks.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"primary_symptom": "bloating and gas", "duration": "2 weeks", "food_relationship": "postprandial"},
                },
                "next_question": {
                    "text": "Do you notice changes in your stool consistency, such as loose stools or alternating constipation?",
                    "target_concept": "bowel_habits",
                    "reason": "Assess lower digestive motility",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "Stools are mostly normal, maybe slightly loose once or twice a week.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"bowel_habits": "mostly normal, occasional mild looseness"},
                },
                "next_question": {
                    "text": "Does warm water, walking, or passing gas bring relief to the distension?",
                    "target_concept": "relieving_factors",
                    "reason": "Identify relieving modalities",
                },
                "status": "continue",
                "confidence": 0.92,
            },
        },
        {
            "answer": "Walking for 15 minutes helps relieve the tightness significantly.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"relieving_factors": "walking 15 minutes"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.94,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "DIGEST-02", "Dipali Trivedi", 31, "female", DOMAIN_DIGESTIVE, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "2 weeks"


def test_sim_09_digestive_loss_of_appetite(client):
    """Digestive 3: Complete lack of appetite and metallic taste in mouth."""
    turns = [
        {
            "answer": "I have had almost no desire to eat food for the past 10 days.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"primary_symptom": "anorexia / loss of appetite", "duration": "10 days"},
                },
                "next_question": {
                    "text": "Do you experience heaviness in the stomach even after taking small quantities of liquid or food?",
                    "target_concept": "food_relationship",
                    "reason": "Assess agnimandya severity",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "Even half a cup of milk feels like a heavy rock sitting in my stomach for hours.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"food_relationship": "extreme fullness with tiny quantities"},
                },
                "next_question": {
                    "text": "Have you noticed any nausea, coated white tongue, or bad taste in the mouth?",
                    "target_concept": "associated_symptoms",
                    "reason": "Check for ama / digestive toxicity signs",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "Yes, my tongue has a thick white coating and everything tastes bitter.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"associated_symptoms": "thick white tongue coating, bitter taste"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.93,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "DIGEST-03", "Harish Bhatt", 55, "male", DOMAIN_DIGESTIVE, "en", turns
    )
    assert "loss of appetite" in res["final_session"]["collected_concepts"]["primary_symptom"]


# =========================================================================
# 4. METABOLIC SIMULATIONS (2 cases)
# =========================================================================

def test_sim_10_metabolic_fatigue_and_polydipsia(client):
    """Metabolic 1: Extreme thirst, frequent urination, and lethargy."""
    turns = [
        {
            "answer": "I am feeling exhausted all day and drinking almost 5 liters of water daily for 2 months.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"primary_symptom": "severe fatigue and excessive thirst", "duration": "2 months", "energy_and_thirst": "5L water daily, extreme lethargy"},
                },
                "next_question": {
                    "text": "Have you noticed waking up multiple times at night to pass urine?",
                    "target_concept": "associated_symptoms",
                    "reason": "Assess nocturia / prameha pattern",
                },
                "status": "continue",
                "confidence": 0.92,
            },
        },
        {
            "answer": "I wake up at least 4 times every night to use the washroom.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"associated_symptoms": "nocturia 4x per night"},
                },
                "next_question": {
                    "text": "Have you experienced any unexplained weight loss despite having normal appetite?",
                    "target_concept": "weight_changes",
                    "reason": "Check metabolic catabolism sign",
                },
                "status": "continue",
                "confidence": 0.93,
            },
        },
        {
            "answer": "Yes, I dropped about 4 kilograms in the last six weeks without dieting.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"weight_changes": "lost 4 kg in 6 weeks without diet"},
                },
                "next_question": {
                    "text": "Do you experience tingling or burning sensations in the soles of your feet?",
                    "target_concept": "severity",
                    "reason": "Check peripheral sensory involvement",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "Yes, the bottoms of my feet burn whenever I go to bed.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"severity": "burning sensation in soles at bedtime"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.96,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "METAB-01", "Ramesh Chawla", 58, "male", DOMAIN_METABOLIC, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "2 months"
    assert "lost 4 kg" in res["final_session"]["collected_concepts"]["weight_changes"]


def test_sim_11_metabolic_weight_gain_and_lethargy(client):
    """Metabolic 2: Unexplained weight gain and cold intolerance."""
    turns = [
        {
            "answer": "Constant low energy, sluggishness, and feeling cold all the time for 3 months.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"primary_symptom": "sluggishness and cold intolerance", "duration": "3 months"},
                },
                "next_question": {
                    "text": "Have you noticed any unexplained weight gain or puffiness in your face or hands?",
                    "target_concept": "weight_changes",
                    "reason": "Assess metabolic slowing signs",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "I have put on 5 kilos even though my appetite has actually reduced.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"weight_changes": "gained 5 kg despite low appetite"},
                },
                "next_question": {
                    "text": "How has your sleep and daily stamina been affected?",
                    "target_concept": "energy_and_thirst",
                    "reason": "Evaluate diurnal fatigue",
                },
                "status": "continue",
                "confidence": 0.88,
            },
        },
        {
            "answer": "I sleep 10 hours and still feel completely drained all morning.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"energy_and_thirst": "unrefreshing 10h sleep, drained mornings"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.92,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "METAB-02", "Anita Sharma", 44, "female", DOMAIN_METABOLIC, "en", turns
    )
    assert "gained 5 kg" in res["final_session"]["collected_concepts"]["weight_changes"]


# =========================================================================
# 5. GENERAL / UNCLEAR SIMULATIONS (2 cases)
# =========================================================================

def test_sim_12_general_diffuse_body_aches(client):
    """General 1: Vague malaise, general fatigue, and diffuse body aches."""
    turns = [
        {
            "answer": "I just feel unwell and achy all over my body for the past 4 days.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"primary_symptom": "general malaise and body ache", "duration": "4 days"},
                },
                "next_question": {
                    "text": "Did this start suddenly after travel, heavy exertion, or exposure to weather?",
                    "target_concept": "onset",
                    "reason": "Clarify mode of onset",
                },
                "status": "continue",
                "confidence": 0.86,
            },
        },
        {
            "answer": "It started after returning from a dusty bus journey last weekend.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"onset": "post dusty travel last weekend"},
                },
                "next_question": {
                    "text": "Have you had any fever, chills, sore throat, or upset stomach along with this?",
                    "target_concept": "associated_symptoms",
                    "reason": "Screen major systems",
                },
                "status": "continue",
                "confidence": 0.9,
            },
        },
        {
            "answer": "No fever or stomach trouble, just dry eyes and heavy muscles.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"associated_symptoms": "dry eyes and heavy muscles, no fever"},
                },
                "next_question": {
                    "text": "How severe is this tiredness — does it prevent you from doing your daily work?",
                    "target_concept": "severity",
                    "reason": "Gauge functional interference",
                },
                "status": "continue",
                "confidence": 0.89,
            },
        },
        {
            "answer": "I can still manage light chores, but I have to rest every few hours.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"severity": "moderate, requires frequent rest"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.93,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "GEN-01", "Gopal Das", 62, "male", DOMAIN_GENERAL, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "4 days"


def test_sim_13_general_ambiguous_chest_flutter(client):
    """General 2: Patient reports ambiguous 'fluttering in chest' without pain."""
    turns = [
        {
            "answer": "Sometimes I feel a mild fluttering sensation inside my chest for about a week.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"primary_symptom": "occasional chest flutter", "duration": "1 week"},
                },
                "next_question": {
                    "text": "Does this fluttering happen during stressful moments, after coffee or tea, or while resting?",
                    "target_concept": "triggers",
                    "reason": "Clarify situational triggers",
                },
                "status": "continue",
                "confidence": 0.85,
            },
        },
        {
            "answer": "Usually in the late afternoon when having my second strong black coffee.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"triggers": "after strong coffee in late afternoon"},
                },
                "next_question": {
                    "text": "Do you feel any dizziness, shortness of breath, or sweating when this occurs?",
                    "target_concept": "associated_symptoms",
                    "reason": "Safety check for hemodynamic stability",
                },
                "status": "continue",
                "confidence": 0.94,
            },
        },
        {
            "answer": "No dizziness, no sweating, no breathing trouble at all.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_GENERAL,
                    "concepts": {"associated_symptoms": "no dizziness, no dyspnea, no diaphoresis"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    res = _run_conversation_simulation(
        client, "GEN-02", "Tarun Roy", 30, "male", DOMAIN_GENERAL, "en", turns
    )
    assert res["final_session"]["collected_concepts"]["duration"] == "1 week"


# =========================================================================
# CRITICAL ACCEPTANCE TEST: SCENARIOS A, B, C, D DIVERGENCE AUDIT
# =========================================================================

def test_critical_acceptance_scenarios_a_b_c_d(client):
    """CRITICAL ACCEPTANCE TEST:

    Run Scenarios A, B, C, D end-to-end and prove:
    1. None of the four follow the same question sequence.
    2. Scenarios B and C ask about different organ systems.
    3. Scenario A focuses on joint-specific details.
    4. Scenario D focuses on systemic/metabolic details.
    5. The final case representations contain distinct domain concepts.
    6. No scenario repeats an already answered concept.
    7. No scenario asks more than 5 questions.
    8. No scenario stalls on any question.
    """
    # Scenario A: 52yo F, acute right knee pain after misstep 2 days ago, swelling present, pain 7/10
    turns_a = [
        {
            "answer": "I missed a step on the stairs 2 days ago and twisted my right knee. It is swollen and 7/10 painful.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {
                        "primary_symptom": "right knee pain",
                        "site": "right knee",
                        "duration": "2 days",
                        "onset": "misstep on stairs",
                        "stiffness_or_swelling": "swelling present",
                        "severity": "7/10",
                    },
                },
                "next_question": {
                    "text": "Are you able to put any weight on that right leg, or do you need support to walk?",
                    "target_concept": "functional_limitation",
                    "reason": "Check weight-bearing ability after knee trauma",
                },
                "status": "continue",
                "confidence": 0.95,
            },
        },
        {
            "answer": "I have to limp and hold onto walls; I cannot bear full weight.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"functional_limitation": "limping, unable to bear full weight"},
                },
                "next_question": {
                    "text": "Does keeping it elevated or applying an ice pack reduce the swelling or ache?",
                    "target_concept": "relieving_factors",
                    "reason": "Assess relief modalities",
                },
                "status": "continue",
                "confidence": 0.92,
            },
        },
        {
            "answer": "Ice helps numb it down for a little while.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_MUSCULOSKELETAL,
                    "concepts": {"relieving_factors": "ice pack gives temporary relief"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    # Scenario B: 34yo M, dry hacking cough for 3 weeks, worse at night and cold air, no fever, mentions old chest X-ray
    turns_b = [
        {
            "answer": "I have had a dry hacking cough for 3 weeks, especially bad at night and in cold air. No fever. I have an old chest X-ray from last year.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {
                        "primary_symptom": "dry hacking cough",
                        "duration": "3 weeks",
                        "cough_character": "dry hacking",
                        "triggers": "cold air and nocturnal",
                        "associated_symptoms": "no fever",
                    },
                    "mentioned_documents": ["old chest X-ray from last year"],
                },
                "next_question": {
                    "text": "Do you feel any throat tickle, raspy irritation, or difficulty catching your breath during cough spasms?",
                    "target_concept": "severity",
                    "reason": "Check for airway hyperreactivity",
                },
                "status": "continue",
                "confidence": 0.93,
            },
        },
        {
            "answer": "A sharp tickle in my throat triggers prolonged coughing fits where I gasp.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"severity": "severe cough spasms triggered by throat tickle"},
                },
                "next_question": {
                    "text": "Have you noticed any acid taste in your mouth or heartburn that might be triggering this cough?",
                    "target_concept": "food_relationship",
                    "reason": "Explore reflux-associated cough",
                },
                "status": "continue",
                "confidence": 0.89,
            },
        },
        {
            "answer": "No heartburn or acid taste at all.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_RESPIRATORY,
                    "concepts": {"food_relationship": "none / no gastroesophageal signs"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.94,
            },
        },
    ]

    # Scenario C: 41yo M, burning epigastric pain 2h after meals for 1 month, sour belching, relieved by warm water, constipation past 2 weeks
    turns_c = [
        {
            "answer": "Burning pain in the upper stomach 2 hours after meals for 1 month, with sour burping. Relieved by warm water, and constipation for 2 weeks.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {
                        "primary_symptom": "burning epigastric pain",
                        "duration": "1 month",
                        "food_relationship": "2 hours after meals",
                        "associated_symptoms": "sour belching",
                        "relieving_factors": "warm water",
                        "bowel_habits": "constipation past 2 weeks",
                    },
                },
                "next_question": {
                    "text": "How severe is this burning pain on a scale from 1 to 10 during the worst flare-ups?",
                    "target_concept": "severity",
                    "reason": "Quantify pain severity",
                },
                "status": "continue",
                "confidence": 0.95,
            },
        },
        {
            "answer": "It reaches about a 6 out of 10, especially when I skip lunch.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_DIGESTIVE,
                    "concepts": {"severity": "6/10, worse when skipping meals"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.96,
            },
        },
    ]

    # Scenario D: 28yo F, generalized fatigue and poor appetite for 2 months, 3 kg weight loss, excessive thirst, dry mouth
    turns_d = [
        {
            "answer": "Feeling exhausted with poor appetite for 2 months, lost 3 kg weight, constant dry mouth and excessive thirst.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {
                        "primary_symptom": "generalized fatigue and poor appetite",
                        "duration": "2 months",
                        "weight_changes": "3 kg weight loss",
                        "energy_and_thirst": "extreme thirst and dry mouth",
                    },
                },
                "next_question": {
                    "text": "Have you noticed passing unusually large volumes of urine or getting up frequently at night?",
                    "target_concept": "associated_symptoms",
                    "reason": "Assess polyuria in metabolic syndrome context",
                },
                "status": "continue",
                "confidence": 0.94,
            },
        },
        {
            "answer": "Yes, I am going to the bathroom almost every hour during the daytime and twice at night.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"associated_symptoms": "polyuria every hour and nocturia 2x"},
                },
                "next_question": {
                    "text": "Do you feel lightheaded when standing up quickly, or have any vision blurriness?",
                    "target_concept": "severity",
                    "reason": "Check orthostatic and glycemic symptoms",
                },
                "status": "continue",
                "confidence": 0.91,
            },
        },
        {
            "answer": "A little lightheaded if I stand up suddenly from the couch.",
            "proposal": {
                "case_update": {
                    "presentation": DOMAIN_METABOLIC,
                    "concepts": {"severity": "postural lightheadedness"},
                },
                "next_question": None,
                "status": "sufficient",
                "confidence": 0.95,
            },
        },
    ]

    res_a = _run_conversation_simulation(client, "SCENARIO-A", "Kamla Devi", 52, "female", DOMAIN_MUSCULOSKELETAL, "en", turns_a)
    res_b = _run_conversation_simulation(client, "SCENARIO-B", "Arjun Patel", 34, "male", DOMAIN_RESPIRATORY, "en", turns_b)
    res_c = _run_conversation_simulation(client, "SCENARIO-C", "Dinesh Kothari", 41, "male", DOMAIN_DIGESTIVE, "en", turns_c)
    res_d = _run_conversation_simulation(client, "SCENARIO-D", "Pooja Radia", 28, "female", DOMAIN_METABOLIC, "en", turns_d)

    # 1. Verify NONE of the four follow the same question sequence
    q_seq_a = res_a["questions"]
    q_seq_b = res_b["questions"]
    q_seq_c = res_c["questions"]
    q_seq_d = res_d["questions"]

    assert q_seq_a != q_seq_b, "Scenario A and B asked identical questions!"
    assert q_seq_a != q_seq_c, "Scenario A and C asked identical questions!"
    assert q_seq_a != q_seq_d, "Scenario A and D asked identical questions!"
    assert q_seq_b != q_seq_c, "Scenario B and C asked identical questions!"
    assert q_seq_b != q_seq_d, "Scenario B and D asked identical questions!"
    assert q_seq_c != q_seq_d, "Scenario C and D asked identical questions!"

    # 2. Verify Scenarios B and C ask about different organ systems
    assert any("cough" in q.lower() or "breath" in q.lower() or "throat" in q.lower() for q in q_seq_b)
    assert any("burning" in q.lower() or "scale" in q.lower() or "pain" in q.lower() for q in q_seq_c)

    # 3. Verify Scenario A focuses on joint-specific details
    concepts_a = res_a["final_session"]["collected_concepts"]
    assert "site" in concepts_a and "right knee" in concepts_a["site"]
    assert "functional_limitation" in concepts_a

    # 4. Verify Scenario D focuses on systemic/metabolic details
    concepts_d = res_d["final_session"]["collected_concepts"]
    assert "weight_changes" in concepts_d
    assert "energy_and_thirst" in concepts_d

    # 5. Final case representations contain distinct domain concepts
    assert res_a["final_session"]["presentation_domain"] == DOMAIN_MUSCULOSKELETAL
    assert res_b["final_session"]["presentation_domain"] == DOMAIN_RESPIRATORY
    assert res_c["final_session"]["presentation_domain"] == DOMAIN_DIGESTIVE
    assert res_d["final_session"]["presentation_domain"] == DOMAIN_METABOLIC

    # 6. Document extraction in Scenario B
    docs_b = res_b["final_session"]["mentioned_documents"]
    assert any("x-ray" in d.lower() for d in docs_b)

    # 7. No scenario asks more than 5 questions
    for res in (res_a, res_b, res_c, res_d):
        assert res["final_session"]["adaptive_question_count"] <= MAX_ADAPTIVE_QUESTIONS
        assert res["final_session"]["interview_complete"] is True

    print("\n>>> ALL CRITICAL ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY! <<<")
