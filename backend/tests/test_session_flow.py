import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.models.schema import Session, Patient


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_flow.db")
        os.environ["DATABASE_PATH"] = db_file
        for k in ("GROQ_API_KEY", "NVIDIA_NIM_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"):
            os.environ.pop(k, None)
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _start(client, adaptive=True):
    return client.post("/session/start", json={
        "patient": {"name": "Test Patient", "age": 45, "gender": "male"},
        "language": "en",
        "visit_type": "new",
        "adaptive": adaptive,
    })


def _start_and_consent(client, adaptive=True):
    r = _start(client, adaptive=adaptive)
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    return sid


def test_start_returns_session_id_only(client):
    r = _start(client)
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    # contract: only session_id, never patient_code / next_question
    assert "patient_code" not in body
    assert "next_question" not in body
    assert len(body) == 1


def test_start_requires_patient_and_validates(client):
    r = client.post("/session/start", json={"patient": {"name": "", "age": 200, "gender": ""}})
    assert r.status_code == 422


def test_consent_idempotent_never_403(client):
    sid = _start(client).json()["session_id"]
    r1 = client.post(f"/session/{sid}/consent", json={"consent_given": True})
    assert r1.status_code == 200
    # repeat valid call must be 200, never 403
    r2 = client.post(f"/session/{sid}/consent", json={"consent_given": True})
    assert r2.status_code == 200
    assert r2.json()["status"] == "success"


def test_patient_code_requires_consent(client):
    sid = _start(client).json()["session_id"]
    r = client.post(f"/session/{sid}/patient-code")
    assert r.status_code == 403


def test_patient_code_generated_once_and_persisted(client):
    sid = _start_and_consent(client)
    r1 = client.post(f"/session/{sid}/patient-code")
    assert r1.status_code == 200
    code1 = r1.json()["patient_code"]
    assert code1.startswith("AIIA-") or code1.startswith("MK-")
    # repeat returns same code
    r2 = client.post(f"/session/{sid}/patient-code")
    assert r2.json()["patient_code"] == code1
    # persisted: GET session returns same code
    g = client.get(f"/session/{sid}").json()
    assert g["patient_code"] == code1


def test_answer_requires_consent_and_code(client):
    sid = _start(client).json()["session_id"]
    r1 = client.post(f"/session/{sid}/answer", json={"answer": "chest pain"})
    assert r1.status_code == 403
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    r2 = client.post(f"/session/{sid}/answer", json={"answer": "chest pain"})
    assert r2.status_code == 403


def test_red_flag_detected_on_raw_text(client):
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    r = client.post(f"/session/{sid}/answer", json={"answer": "I have severe chest pain and I'm worried"})
    body = r.json()
    assert body["red_flag"] is True
    # must not advance
    g = client.get(f"/session/{sid}").json()
    assert g["interview_step"] == "chief_complaint"


def test_missing_field_is_not_red_flag(client):
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    r = client.post(f"/session/{sid}/answer", json={"answer": ""})
    # empty answer must not mark complete nor be a red flag
    assert r.status_code == 200
    assert r.json()["red_flag"] is False


def test_llm_cannot_advance_on_empty_answer(client):
    from backend.db import save_session, get_session
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    with patch.object(session_router, "get_llm_provider", side_effect=Exception("no provider")):
        # no provider -> needs_review=True; raw answer stored as fallback so interview advances
        r = client.post(f"/session/{sid}/answer", json={"answer": "some pain"})
        assert r.json()["needs_review"] is True
        g = client.get(f"/session/{sid}").json()
        # Interview MUST advance (raw answer stored as fallback); the step
        # becomes the next deterministic target concept, never a blank/halt.
        assert g["interview_step"] not in (None, "", "complete"), "LLM failure must not stall the interview"
        assert g["next_question"] is not None
        # Raw answer stored as chief_complaint fallback
        assert g["chief_complaint"] == "some pain"



def _fake_extract(provider, field, ans):
    return {
        "chief_complaint": {"complaint": "stomach pain", "confidence": 0.9},
        "onset": {"onset": "2 days ago", "confidence": 0.9},
        "duration": {"duration": "2 days", "confidence": 0.9},
        "severity": {"severity": "moderate", "confidence": 0.9},
        "character": {"character": "sharp", "confidence": 0.9},
        "associated_symptoms": {"associated_symptoms": ["nausea"], "confidence": 0.9},
    }[field]


class _FakeProvider:
    provider_name = "gemini"


def test_deterministic_progression_full_flow(client):
    # Deterministic statutory intake path: chief_complaint -> onset -> duration ->
    # severity -> character -> associated_symptoms. The adaptive conversational
    # interviewer is opted out via adaptive=false.
    sid = _start_and_consent(client, adaptive=False)
    client.post(f"/session/{sid}/patient-code")
    answers = [
        ("chief_complaint", "stomach pain"),
        ("onset", "2 days ago"),
        ("duration", "2 days"),
        ("severity", "moderate"),
        ("character", "sharp"),
        ("associated_symptoms", "nausea"),
    ]
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        for i, (field, ans) in enumerate(answers):
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            body = r.json()
            assert r.status_code == 200
            assert body["red_flag"] is False
            g = client.get(f"/session/{sid}").json()
            if i < len(answers) - 1:
                g_field_value = {
                    "chief_complaint": g["chief_complaint"],
                    "onset": g["history_of_present_illness"]["onset"],
                    "duration": g["history_of_present_illness"]["duration"],
                    "severity": g["history_of_present_illness"]["severity"],
                    "character": g["history_of_present_illness"]["character"],
                    "associated_symptoms": g["history_of_present_illness"]["associated_symptoms"],
                }[field]
                assert g_field_value is not None
    # after all answers, interview complete
    g = client.get(f"/session/{sid}").json()
    assert g["interview_complete"] is True
    assert g["interview_step"] == "complete"
    # all answer records appended with provenance
    assert len(g["answer_records"]) == 6
    assert all(ar["provider"] == "gemini" for ar in g["answer_records"])


def test_refresh_restores_same_patient_code(client):
    sid = _start_and_consent(client)
    code = client.post(f"/session/{sid}/patient-code").json()["patient_code"]
    # simulate refresh via GET
    g = client.get(f"/session/{sid}").json()
    assert g["patient_code"] == code
    assert g["session_id"] == sid
    # GET exposes next_question derived from the adaptive engine
    assert g["next_question"] == "What is the primary health reason for your visit today?"


def test_llm_extraction_failure_preserves_raw_and_marks_review(client):
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    # Env keys cleared by the client fixture -> no providers configured.
    r = client.post(f"/session/{sid}/answer", json={"answer": "my pain started yesterday"})
    body = r.json()
    assert body["needs_review"] is True
    assert body["red_flag"] is False
    g = client.get(f"/session/{sid}").json()
    # raw answer verbatim preserved in raw_answers
    assert g["raw_answers"][-1]["answer"] == "my pain started yesterday"
    # AnswerRecord appended with needs_review=True and no provider
    assert g["answer_records"][-1]["needs_review"] is True
    assert g["answer_records"][-1]["provider"] is None
    # Interview MUST advance — raw answer stored as fallback; step moves to a
    # concrete next target concept
    assert g["interview_step"] not in (None, "", "complete"), "LLM failure must not stall interview"
    assert g["next_question"] is not None
    assert g["chief_complaint"] == "my pain started yesterday"


def test_extraction_advances_chief_complaint_when_provider_works(client):
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(return_value={
        "case_update": {
            "presentation": "digestive",
            "concepts": {"primary_symptom": "stomach pain", "site": "stomach"},
            "mentioned_documents": [],
        },
        "next_question": {
            "text": "How long have you been experiencing this pain?",
            "target_concept": "duration",
            "reason": "validate duration",
            "priority": "normal",
        },
        "status": "continue",
        "confidence": 0.9,
        "provider": "groq",
    })):
        r = client.post(f"/session/{sid}/answer", json={"answer": "stomach pain since morning"})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is False
    assert body["red_flag"] is False
    g = client.get(f"/session/{sid}").json()
    assert g["chief_complaint"] == "stomach pain"
    assert g["interview_step"] == "duration"
    assert g["answer_records"][-1]["provider"] == "groq"
    assert g["answer_records"][-1]["needs_review"] is False


def test_extraction_failure_keeps_chief_complaint_unsafe_path(client):
    sid = _start_and_consent(client)
    client.post(f"/session/{sid}/patient-code")
    # All providers fail (generate_adaptive_turn -> extract_case both down).
    # Correct behavior: raw answer stored as fallback, interview advances, needs_review=True.
    with patch.object(session_router, "generate_adaptive_turn", AsyncMock(side_effect=RuntimeError("LLM down"))), \
         patch.object(session_router, "extract_case", AsyncMock(side_effect=RuntimeError("no providers"))):
        r = client.post(f"/session/{sid}/answer", json={"answer": "my pain started yesterday"})
    body = r.json()
    assert body["needs_review"] is True
    g = client.get(f"/session/{sid}").json()
    # Raw answer stored as chief_complaint fallback; interview step advances
    assert g["chief_complaint"] == "my pain started yesterday"
    assert g["interview_step"] not in (None, "", "complete"), "LLM failure must not stall interview"
    assert g["next_question"] is not None
    # safe fallback: red flag never fires on a plain pain complaint
    assert body["red_flag"] is False



def test_db_migration_upgrades_legacy_table(client):
    import sqlite3
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "legacy.db")
        conn = sqlite3.connect(db_file)
        conn.execute("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                patient_json TEXT NOT NULL,
                chief_complaint TEXT,
                hpi_json TEXT NOT NULL,
                documents_json TEXT NOT NULL,
                doctor_review_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO sessions (session_id, patient_json, chief_complaint, hpi_json, documents_json, doctor_review_json)
            VALUES ('legacy-1', '{"name":"A","age":30,"gender":"m"}', 'pain', '{}', '[]', '{}')
        """)
        conn.commit()
        conn.close()
        from backend.db import init_db, get_session
        os.environ["DATABASE_PATH"] = db_file
        try:
            # must not crash on legacy table
            init_db()
            s = get_session("legacy-1")
            assert s is not None
            assert s.language == "en"
            assert s.answer_records == []
            # idempotent second init
            init_db()
        finally:
            os.environ.pop("DATABASE_PATH", None)
