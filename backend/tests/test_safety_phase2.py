import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_safety.db")
        os.environ["DATABASE_PATH"] = db_file
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start_and_code(client):
    r = client.post("/session/start", json={
        "patient": {"name": "Test Patient", "age": 45, "gender": "male"},
        "language": "en",
        "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def _fake_extract_case(ans, current_concept=None, domain_hint=None):
    values = {
        "primary_symptom": "stomach pain",
        "onset": "2 days ago",
        "duration": "2 days",
        "severity": "moderate",
        "character": "sharp",
        "associated_symptoms": ["nausea"],
    }
    return {
        "domain": "general",
        "concepts": {current_concept: values.get(current_concept)},
        "confidence": 0.9,
        "mentioned_documents": [],
        "provider": "gemini",
    }


def test_raw_red_flag_text_is_flagged(client):
    sid = _start_and_code(client)
    r = client.post(f"/session/{sid}/answer", json={"answer": "I have severe chest pain and I'm scared"})
    assert r.json()["red_flag"] is True


def test_safe_answer_is_not_flagged(client):
    sid = _start_and_code(client)
    r = client.post(f"/session/{sid}/answer", json={"answer": "I have a mild stomach ache"})
    assert r.json()["red_flag"] is False


def test_raw_detection_survives_llm_failure(client):
    sid = _start_and_code(client)
    # no provider configured -> extract_case raises, but safety screening runs
    # BEFORE extraction, so a flagged answer is still caught
    r = client.post(f"/session/{sid}/answer", json={"answer": "difficulty breathing and chest pain"})
    assert r.json()["red_flag"] is True


def test_provider_unavailable_does_not_bypass_safety(client):
    sid = _start_and_code(client)
    # no providers configured -> extract_case raises. Safe path => needs_review.
    r = client.post(f"/session/{sid}/answer", json={"answer": "carrying breathing problems"})
    assert r.status_code == 200
    # red flag still caught on a genuinely flagged answer without any provider
    r2 = client.post(f"/session/{sid}/answer", json={"answer": "I feel unconscious coming on"})
    assert r2.json()["red_flag"] is True


def test_incomplete_fields_not_emergency(client):
    sid = _start_and_code(client)
    r = client.post(f"/session/{sid}/answer", json={"answer": ""})
    assert r.status_code == 200
    assert r.json()["red_flag"] is False
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is False


def test_flagged_session_cannot_get_token(client):
    sid = _start_and_code(client)
    client.post(f"/session/{sid}/answer", json={"answer": "chest pain"})
    # safety flagged persisted
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is True
    # a flagged session cannot receive another normal queue token
    r = client.post(f"/session/{sid}/patient-code")
    assert r.status_code == 403


def test_flagged_session_persists_across_refresh(client):
    sid = _start_and_code(client)
    client.post(f"/session/{sid}/answer", json={"answer": "severe bleeding from a wound"})
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is True
    assert g["safety_detail"]  # matched term recorded
    assert g["safety_flag_time"] is not None


def test_flagged_session_shows_in_emergency_dashboard(client):
    safe_sid = _start_and_code(client)
    flagged_sid = _start_and_code(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        r = client.post(f"/session/{safe_sid}/answer", json={"answer": "mild headache"})
        assert r.json()["red_flag"] is False
    client.post(f"/session/{flagged_sid}/answer", json={"answer": "chest tightness radiating to the arm"})

    em = client.get("/doctor/emergency").json()
    codes = {e["patient_code"] for e in em}
    assert flagged_sid in [e["session_id"] for e in em]
    assert safe_sid not in [e["session_id"] for e in em]


def test_safe_session_remains_eligible(client):
    sid = _start_and_code(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        client.post(f"/session/{sid}/answer", json={"answer": "stomach pain"})
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is False
    # not in emergency list
    em = client.get("/doctor/emergency").json()
    assert sid not in [e["session_id"] for e in em]


def test_d01_excludes_flagged_sessions(client):
    safe_sid = _start_and_code(client)
    flagged_sid = _start_and_code(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        client.post(f"/session/{safe_sid}/answer", json={"answer": "mild headache"})
    client.post(f"/session/{flagged_sid}/answer", json={"answer": "cardiac arrest"})
    sessions = client.get("/doctor/sessions").json()
    ids = {s["session_id"] for s in sessions}
    assert safe_sid in ids
    assert flagged_sid not in ids


def test_flagged_session_cannot_enter_normal_queue_progression(client):
    sid = _start_and_code(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        # complete a normal interview first
        for ans in ["stomach pain", "2 days ago", "2 days", "moderate", "sharp", "nausea"]:
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
        assert r.json()["session_complete"] is True
        # a later flagged answer must override to red flag, never a normal summary
        r2 = client.post(f"/session/{sid}/answer", json={"answer": "chest pain"})
    assert r2.json()["red_flag"] is True
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is True


def test_red_flag_from_structured_state(client):
    # A red flag that only lands in structured HPI state (not the raw text)
    # must still be caught by the deterministic structured-state screen.
    sid = _start_and_code(client)
    # direct raw text without red flag -> not flagged
    r = client.post(f"/session/{sid}/answer", json={"answer": "please note my symptoms below"})
    assert r.json()["red_flag"] is False
    from backend.db import get_session as db_get
    s = db_get(sid)
    s.history_of_present_illness.associated_symptoms = ["shortness of breath"]
    from backend.db import save_session as db_save
    db_save(s)
    r2 = client.post(f"/session/{sid}/answer", json={"answer": "nothing to add"})
    assert r2.json()["red_flag"] is True


def test_direct_emergency_endpoint_flags_and_alerts(client):
    sid = _start_and_code(client)
    res = client.post(f"/session/{sid}/emergency")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "emergency_alerted"
    assert "Staff has been alerted" in data["message"]

    sess = client.get(f"/session/{sid}").json()
    assert sess["safety_flagged"] is True
    assert any("emergency" in str(d).lower() for d in sess["safety_detail"])

    em = client.get("/doctor/emergency").json()
    assert sid in [e["session_id"] for e in em]


# ---------------------------------------------------------------------------
# Graph D: spec-sourced escalation phrases + multilingual twins.
# Source: clinical_interview_spec_v1.md §4.5/5.5/6.5, packet GI-10..13,
# MS-11..14, RS-10..14. Combination presentations need clinician thresholds
# and are deliberately NOT encoded (questionnaire §2.4 pending).
# ---------------------------------------------------------------------------

def test_spec_bleeding_flags_are_caught(client):
    from backend.rules.safety_rules import evaluate_safety
    from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview

    def blank():
        return Session(session_id="x", patient=Patient(name="P", age=30, gender="m"),
                       history_of_present_illness=HistoryOfPresentIllness(),
                       doctor_review=DoctorReview())

    for text in ["I am vomiting blood.", "My stool is black and tarry.",
                 "Blood in my sputum this morning.", "I am coughing up blood."]:
        assert evaluate_safety(text, blank()).flagged is True, text


def test_spec_systemic_flags_are_caught(client):
    from backend.rules.safety_rules import evaluate_safety
    from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview

    def blank():
        return Session(session_id="x", patient=Patient(name="P", age=30, gender="m"),
                       history_of_present_illness=HistoryOfPresentIllness(),
                       doctor_review=DoctorReview())

    for text in ["My eyes have turned yellow.", "I cannot bear weight on my leg.",
                 "My lips turned blue.", "I have a hot swollen joint with fever.",
                 "I cannot swallow food.", "I am choking."]:
        assert evaluate_safety(text, blank()).flagged is True, text


def test_hindi_gujarati_red_flags_escalate_like_english(client):
    sid = _start_and_code(client)
    r = client.post(f"/session/{sid}/answer", json={"answer": "मुझे सीने में दर्द है"})
    assert r.json()["red_flag"] is True
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is True
    assert g["safety_detail"] == ["सीने में दर्द"]

    sid2 = _start_and_code(client)
    r2 = client.post(f"/session/{sid2}/answer", json={"answer": "મને છાતીમાં દુખાવો છે"})
    assert r2.json()["red_flag"] is True
    assert client.get(f"/session/{sid2}").json()["safety_flagged"] is True


def test_benign_utterances_are_not_flagged(client):
    from backend.rules.safety_rules import evaluate_safety
    from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview

    def blank():
        return Session(session_id="x", patient=Patient(name="P", age=30, gender="m"),
                       history_of_present_illness=HistoryOfPresentIllness(),
                       doctor_review=DoctorReview())

    for text in ["I have mild acidity after meals.", "मुझे हल्की गैस है",
                 "My knee aches when climbing stairs.",
                 "Yellow dal is my favourite food."]:
        assert evaluate_safety(text, blank()).flagged is False, text


def test_safety_gate_runs_before_llm_and_persists_audit(client):
    # LLM down + red-flag answer -> safety still catches, audits, blocks token.
    sid = _start_and_code(client)
    r = client.post(f"/session/{sid}/answer", json={"answer": "vomiting blood since morning"})
    assert r.json()["red_flag"] is True
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is True
    assert g["safety_flag_time"] is not None
    assert any("blood" in str(d).lower() for d in g["safety_detail"])
    assert any(a.get("red_flag") for a in g["raw_answers"])
    tok = client.post(f"/session/{sid}/token")
    assert tok.status_code == 403

