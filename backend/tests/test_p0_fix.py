"""Regression tests for the P0 FINAL FIX PASS.

Finding 2  - P06 document step is now persisted and gates the queue token.
Finding 4  - /doctor/* is loopback-only (demo-level, not auth).
Finding 5  - answer needs_review is surfaced to the doctor; token policy is
             unchanged (flagged interview answers never block the token because
             the completed interview always yields structured HPI the doctor
             reviews in D02/D03 — only documents and safety gate tokens).
"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.routers.doctor import require_loopback
from backend.db import get_session as db_get_session, save_session as db_save_session


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_PATH"] = os.path.join(tmpdir, "p0_fix.db")
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _fake_extract_case(ans, current_concept=None, domain_hint=None):
    values = {
        "primary_symptom": "katishoola",
        "onset": "1 week ago",
        "duration": "1 week",
        "severity": "moderate",
        "character": "dull",
        "associated_symptoms": ["stiffness"],
    }
    return {
        "domain": "general",
        "concepts": {current_concept: values.get(current_concept)},
        "confidence": 0.9,
        "mentioned_documents": [],
        "provider": "gemini",
    }


_INTERVIEW = ["katishoola", "1 week ago", "1 week", "moderate", "dull", "stiffness"]


def _start(client, name="Fix Patient"):
    sid = client.post("/session/start", json={
        "patient": {"name": name, "age": 40, "gender": "female"},
        "language": "en", "visit_type": "new",
    }).json()["session_id"]
    assert client.post(f"/session/{sid}/consent", json={"consent_given": True}).status_code == 200
    assert client.post(f"/session/{sid}/patient-code").status_code == 200
    return sid


def _complete_interview(client, sid):
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        for ans in _INTERVIEW:
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            assert r.status_code == 200
    s = client.get(f"/session/{sid}").json()
    assert s["interview_complete"] is True
    return s


# ---------------------------------------------------------------------------
# Finding 2 — P06 document step authoritative + resume correctness
# ---------------------------------------------------------------------------

def test_f2_incomplete_document_step_blocks_token(client):
    sid = _start(client)
    s = _complete_interview(client, sid)

    # interview done but P06 not recorded -> refresh sees the incomplete step
    assert s["interview_complete"] is True
    assert s["document_intake_done"] is False

    # a refresh/GET cannot silently bypass P06 to mint a token
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "incomplete_document_step"


def test_f2_documents_complete_persists_and_permits_token(client):
    sid = _start(client)
    _complete_interview(client, sid)

    # idempotent persistence
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    assert client.get(f"/session/{sid}").json()["document_intake_done"] is True

    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    assert r.json()["token"].startswith("KY-")


def test_f2_documents_complete_not_found(client):
    assert client.post("/session/does-not-exist/documents-complete").status_code == 404


def test_f2_safety_flag_still_overrides_documents_complete(client):
    sid = _start(client)
    client.post(f"/session/{sid}/answer", json={"answer": "severe chest pain"})
    # F-06: flagged sessions have incomplete interview, so documents-complete
    # is now rejected with 403 (incomplete_interview)
    r = client.post(f"/session/{sid}/documents-complete")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "incomplete_interview"
    # Token still correctly blocked by safety gate
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "safety_flagged"


# ---------------------------------------------------------------------------
# Finding 4 — loopback demo gate on /doctor/*
# ---------------------------------------------------------------------------

def test_f4_loopback_gate_allowlist():
    assert require_loopback(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))) is None
    assert require_loopback(SimpleNamespace(client=SimpleNamespace(host="::1"))) is None
    assert require_loopback(SimpleNamespace(client=SimpleNamespace(host="localhost"))) is None
    assert require_loopback(SimpleNamespace(client=SimpleNamespace(host="testclient"))) is None


def test_f4_loopback_gate_rejects_lan_client():
    with pytest.raises(HTTPException) as exc:
        require_loopback(SimpleNamespace(client=SimpleNamespace(host="192.168.1.42")))
    assert exc.value.status_code == 403


def test_f4_loopback_gate_does_not_block_normal_testclient_flow(client):
    # TestClient presents as "testclient" (allowlisted) so doctor endpoints still work
    sid = _start(client)
    _complete_interview(client, sid)
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    assert client.post(f"/session/{sid}/token").status_code == 200
    assert client.get("/doctor/emergency").status_code == 200
    assert client.get("/doctor/queue").status_code == 200
    r = client.get(f"/doctor/session/{sid}")
    assert r.json()["patient_code"].startswith("AIIA-") or r.json()["patient_code"].startswith("MK-")


# ---------------------------------------------------------------------------
# Finding 5 — answer needs_review surfaced to doctor; token policy unchanged
# ---------------------------------------------------------------------------

def test_f5_flagged_answer_visible_to_doctor_and_token_policy(client):
    sid = _start(client)
    _complete_interview(client, sid)

    # simulate an LLM-extraction hiccup during the interview (raw answer kept,
    # structured field still present because the field eventually completed)
    s = db_get_session(sid)
    assert s is not None
    s.answer_records[0].needs_review = True
    db_save_session(s)

    # surfaced to the doctor in D02
    d2 = client.get(f"/doctor/session/{sid}")
    assert d2.status_code == 200
    body = d2.json()
    flagged = [r for r in body["answer_records"] if r["needs_review"]]
    assert len(flagged) >= 1
    assert flagged[0]["answer"] == "katishoola"  # raw answer preserved

    # token policy decision (documented in test module docstring): flagged
    # interview answers do NOT block the token; the doctor reviews the
    # structured HPI. Documents and safety remain the only gates.
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    assert r.json()["token"].startswith("KY-")


def test_f2_documents_complete_failure_does_not_persist_and_returns_error(client):
    sid = _start(client)
    _complete_interview(client, sid)
    # simulate a failure in the documents-complete endpoint
    with patch("backend.routers.session.db_save_session") as mock_save:
        mock_save.side_effect = Exception("DB down")
        r = client.post(f"/session/{sid}/documents-complete")
        print(f"[DEBUG] Mock save called: {mock_save.called}")
        print(f"[DEBUG] Mock save call count: {mock_save.call_count}")
        print(f"[DEBUG] Response status: {r.status_code}")
        print(f"[DEBUG] Response text: {r.text}")
        s = client.get(f"/session/{sid}").json()
        print(f"[DEBUG] Session document_intake_done after POST: {s['document_intake_done']}")
        assert r.status_code == 500
        # ensure flag not set
        assert s["document_intake_done"] is False


# ---------------------------------------------------------------------------
# F-06 — documents-complete requires completed interview
# ---------------------------------------------------------------------------

def test_f6_incomplete_interview_blocks_documents_complete(client):
    """(a) incomplete interview → POST /documents-complete => 403"""
    sid = _start(client)
    # No interview answers, interview_complete is False
    r = client.post(f"/session/{sid}/documents-complete")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "incomplete_interview"
    assert client.get(f"/session/{sid}").json()["document_intake_done"] is False


def test_f6_completed_interview_permits_documents_complete(client):
    """(b) completed interview → POST /documents-complete => 200"""
    sid = _start(client)
    _complete_interview(client, sid)
    r = client.post(f"/session/{sid}/documents-complete")
    assert r.status_code == 200
    assert client.get(f"/session/{sid}").json()["document_intake_done"] is True


def test_f6_incomplete_interview_blocks_token(client):
    """(c) incomplete interview cannot obtain token"""
    sid = _start(client)
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "incomplete_session"


def test_f6_safety_flagged_session_still_blocked_at_token(client):
    """(d) safety-flagged sessions remain blocked at token endpoint"""
    sid = _start(client)
    client.post(f"/session/{sid}/answer", json={"answer": "stroke symptoms"})
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "safety_flagged"