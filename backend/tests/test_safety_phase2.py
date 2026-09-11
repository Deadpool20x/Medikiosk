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


class _FakeProvider:
    provider_name = "gemini"


def _fake_extract(provider, field, ans):
    return {
        "chief_complaint": {"complaint": "stomach pain", "confidence": 0.9},
        "onset": {"onset": "2 days ago", "confidence": 0.9},
        "duration": {"duration": "2 days", "confidence": 0.9},
        "severity": {"severity": "moderate", "confidence": 0.9},
        "character": {"character": "sharp", "confidence": 0.9},
        "associated_symptoms": {"associated_symptoms": ["nausea"], "confidence": 0.9},
    }[field]


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
    with patch.object(session_router, "get_llm_provider", side_effect=Exception("no provider")):
        # safety must trigger BEFORE extraction is even attempted
        r = client.post(f"/session/{sid}/answer", json={"answer": "difficulty breathing and chest pain"})
    assert r.json()["red_flag"] is True


def test_provider_unavailable_does_not_bypass_safety(client):
    sid = _start_and_code(client)
    # no providers configured -> get_llm_provider raises. Safe path => needs_review.
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
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        r = client.post(f"/session/{safe_sid}/answer", json={"answer": "mild headache"})
        assert r.json()["red_flag"] is False
    client.post(f"/session/{flagged_sid}/answer", json={"answer": "chest tightness radiating to the arm"})

    em = client.get("/doctor/emergency").json()
    codes = {e["patient_code"] for e in em}
    assert flagged_sid in [e["session_id"] for e in em]
    assert safe_sid not in [e["session_id"] for e in em]


def test_safe_session_remains_eligible(client):
    sid = _start_and_code(client)
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        client.post(f"/session/{sid}/answer", json={"answer": "stomach pain"})
    g = client.get(f"/session/{sid}").json()
    assert g["safety_flagged"] is False
    # not in emergency list
    em = client.get("/doctor/emergency").json()
    assert sid not in [e["session_id"] for e in em]


def test_d01_excludes_flagged_sessions(client):
    safe_sid = _start_and_code(client)
    flagged_sid = _start_and_code(client)
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        client.post(f"/session/{safe_sid}/answer", json={"answer": "mild headache"})
    client.post(f"/session/{flagged_sid}/answer", json={"answer": "cardiac arrest"})
    sessions = client.get("/doctor/sessions").json()
    ids = {s["session_id"] for s in sessions}
    assert safe_sid in ids
    assert flagged_sid not in ids


def test_flagged_session_cannot_enter_normal_queue_progression(client):
    sid = _start_and_code(client)
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
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
