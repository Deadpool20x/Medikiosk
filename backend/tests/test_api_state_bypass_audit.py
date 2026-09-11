"""
MediKiosk — Final API State / Bypass Audit (All 8 Invariants)

Invariants tested:
1. Incomplete interview:
   POST /session/{id}/documents-complete -> 403 incomplete_interview
   POST /session/{id}/token -> 403 incomplete_session/pending state

2. Safety-flagged session:
   POST /session/{id}/token -> 403 safety_flagged
   POST /session/{id}/upload -> 403 safety_flagged
   PATCH /doctor/session/{id} doctor_confirmed=true -> 409
   safety_flagged remains true

3. Document state:
   incomplete document step -> token rejected (403)
   completed document step -> token permitted when all other requirements pass (200)

4. Invalid session:
   state-changing endpoint -> 404

5. Validation:
   malformed patient payload -> 422
   empty upload -> 400
   wrong MIME -> 400
   magic/MIME mismatch -> 400
   corrupted image -> 400
   oversized upload (>8MB) -> 413

6. Department routing:
   Kayachikitsa token only enters Kayachikitsa queue
   Panchakarma token only enters Panchakarma queue
   safety cases enter neither normal queue

7. Doctor:
   non-flagged completed case can be confirmed
   flagged case cannot be confirmed

8. No mutation should occur when a prohibited request is rejected.
"""
import copy
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview
from backend.routers import session as session_router

ROOT = Path(__file__).resolve().parents[2]
PNG_FIXTURE = ROOT / "frontend" / "sample-prescription.png"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_bypass_audit.db")
        os.environ["DATABASE_PATH"] = db_file
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


class _FakeProvider:
    provider_name = "groq"


def _fake_extract(provider, field, ans):
    return {
        "chief_complaint": {"complaint": "stomach pain", "confidence": 0.9},
        "onset": {"onset": "2 days ago", "confidence": 0.9},
        "duration": {"duration": "2 days", "confidence": 0.9},
        "severity": {"severity": "moderate", "confidence": 0.9},
        "character": {"character": "sharp", "confidence": 0.9},
        "associated_symptoms": {"associated_symptoms": ["nausea"], "confidence": 0.9},
    }[field]


def _start_consent_code(client, name="Audit Patient"):
    r = client.post("/session/start", json={
        "patient": {"name": name, "age": 40, "gender": "female"},
        "language": "en",
        "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def _complete_interview(client, sid, complaint="stomach pain"):
    def _extract(p, field, ans):
        d = _fake_extract(p, field, ans)
        if field == "chief_complaint":
            d = {"complaint": complaint, "confidence": 0.9}
        return d

    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_extract):
        for ans in [complaint, "2 days ago", "2 days", "moderate", "sharp", "nausea"]:
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            assert r.status_code == 200
        assert r.json()["session_complete"] is True


# ==============================================================================
# INVARIANT 1: Incomplete interview
# ==============================================================================
def test_invariant_1_incomplete_interview_rejects_docs_complete_and_token(client):
    sid = _start_consent_code(client)

    # 1. POST /session/{id}/documents-complete -> 403 incomplete_interview
    r_docs = client.post(f"/session/{sid}/documents-complete")
    assert r_docs.status_code == 403, f"Expected 403, got {r_docs.status_code}"
    assert r_docs.json()["detail"]["error"] == "incomplete_interview"

    # 2. POST /session/{id}/token -> 403 incomplete_session
    r_token = client.post(f"/session/{sid}/token")
    assert r_token.status_code == 403, f"Expected 403, got {r_token.status_code}"
    assert r_token.json()["detail"]["error"] == "incomplete_session"


# ==============================================================================
# INVARIANT 2: Safety-flagged session
# ==============================================================================
def test_invariant_2_safety_flagged_session_blocked_and_immutable(client):
    sid = _start_consent_code(client)

    # Trigger deterministic safety flag
    r_ans = client.post(f"/session/{sid}/answer", json={"answer": "I have crushing chest pain and shortness of breath"})
    assert r_ans.status_code == 200
    assert r_ans.json()["red_flag"] is True

    # Check state before attempted bypasses
    session_before = client.get(f"/session/{sid}").json()
    assert session_before["safety_flagged"] is True

    # 1. POST /session/{id}/token -> 403 safety_flagged
    r_tok = client.post(f"/session/{sid}/token")
    assert r_tok.status_code == 403
    assert r_tok.json()["detail"]["error"] == "safety_flagged"

    # 2. POST /session/{id}/upload -> 403 safety review required
    r_up = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", PNG_FIXTURE.read_bytes(), "image/png")})
    assert r_up.status_code == 403

    # 3. PATCH /doctor/session/{id} doctor_confirmed=true -> 409
    r_doc = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r_doc.status_code == 409

    # 4. Verify safety_flagged remains true and doctor_confirmed remains false
    session_after = client.get(f"/session/{sid}").json()
    assert session_after["safety_flagged"] is True
    assert session_after["doctor_review"]["confirmed"] is False
    assert session_after["queue_token"] is None


# ==============================================================================
# INVARIANT 3: Document state
# ==============================================================================
def test_invariant_3_document_state_progression(client):
    sid = _start_consent_code(client)
    _complete_interview(client, sid)

    # Prior to completing documents step, token is rejected
    r_tok_early = client.post(f"/session/{sid}/token")
    assert r_tok_early.status_code == 403
    assert r_tok_early.json()["detail"]["error"] == "incomplete_document_step"

    # Mark document step complete (skip or uploaded)
    r_finish = client.post(f"/session/{sid}/documents-complete")
    assert r_finish.status_code == 200

    # Token now permitted when all other requirements pass
    r_tok_ok = client.post(f"/session/{sid}/token")
    assert r_tok_ok.status_code == 200
    body = r_tok_ok.json()
    assert "token" in body and body["token"].startswith("KY-")


# ==============================================================================
# INVARIANT 4: Invalid session -> 404
# ==============================================================================
def test_invariant_4_invalid_session_returns_404(client):
    bogus = "non-existent-session-id"

    # State-changing endpoints
    assert client.post(f"/session/{bogus}/consent", json={"consent_given": True}).status_code == 404
    assert client.post(f"/session/{bogus}/patient-code").status_code == 404
    assert client.post(f"/session/{bogus}/answer", json={"answer": "hello"}).status_code == 404
    assert client.post(f"/session/{bogus}/upload", files={"file": ("rx.png", PNG_FIXTURE.read_bytes(), "image/png")}).status_code == 404
    assert client.post(f"/session/{bogus}/documents-complete").status_code == 404
    assert client.post(f"/session/{bogus}/token").status_code == 404
    assert client.patch(f"/session/{bogus}/document/0", json={"corrected_value": "test"}).status_code == 404
    assert client.patch(f"/doctor/session/{bogus}", json={"doctor_confirmed": True}).status_code == 404
    assert client.patch(f"/doctor/session/{bogus}/document/0", json={"corrected_value": "test"}).status_code == 404


# ==============================================================================
# INVARIANT 5: Validation
# ==============================================================================
def test_invariant_5_validation_rejections(client):
    # 1. Malformed patient payload -> 422
    r_mal = client.post("/session/start", json={"patient": {"name": "", "age": -5, "gender": ""}})
    assert r_mal.status_code == 422

    sid = _start_consent_code(client)

    # 2. Empty upload -> 400
    r_empty = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", b"", "image/png")})
    assert r_empty.status_code == 400
    assert "empty" in r_empty.json()["detail"].lower()

    # 3. Wrong MIME -> 400
    r_wrong_mime = client.post(f"/session/{sid}/upload", files={"file": ("rx.txt", b"plain text", "text/plain")})
    assert r_wrong_mime.status_code == 400
    assert "Unsupported file type" in r_wrong_mime.json()["detail"]

    # 4. Magic / MIME mismatch -> 400
    # True PNG fixture lying about being JPEG
    r_mismatch = client.post(f"/session/{sid}/upload", files={"file": ("rx.jpg", PNG_FIXTURE.read_bytes(), "image/jpeg")})
    assert r_mismatch.status_code == 400
    assert "not a valid image" in r_mismatch.json()["detail"]

    # 5. Corrupted image -> 400
    valid = bytearray(PNG_FIXTURE.read_bytes())
    for i in range(16, len(valid)):
        valid[i] ^= 0xFF
    r_corrupt = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", bytes(valid), "image/png")})
    assert r_corrupt.status_code == 400

    # 6. Oversized upload (> 8MB) -> 413
    big = PNG_MAGIC + b"\x00" * (8 * 1024 * 1024 + 10)
    r_big = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", big, "image/png")})
    assert r_big.status_code == 413


# ==============================================================================
# INVARIANT 6: Department routing separation
# ==============================================================================
def test_invariant_6_department_routing_separation(client):
    # 1. Kayachikitsa case
    ky_sid = _start_consent_code(client, name="Kaya Patient")
    _complete_interview(client, ky_sid, complaint="stomach pain and indigestion")
    client.post(f"/session/{ky_sid}/documents-complete")
    ky_tok = client.post(f"/session/{ky_sid}/token").json()
    assert ky_tok["department"] == "Kayachikitsa"
    assert ky_tok["token"].startswith("KY-")

    # 2. Panchakarma case
    pk_sid = _start_consent_code(client, name="Pancha Patient")
    _complete_interview(client, pk_sid, complaint="Sthaulya and obesity management")
    client.post(f"/session/{pk_sid}/documents-complete")
    pk_tok = client.post(f"/session/{pk_sid}/token").json()
    assert pk_tok["department"] == "Panchakarma"
    assert pk_tok["token"].startswith("PK-")

    # 3. Safety case
    safe_sid = _start_consent_code(client, name="Safety Patient")
    client.post(f"/session/{safe_sid}/answer", json={"answer": "severe chest pain"})

    # Inspect queues
    ky_queue = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    pk_queue = client.get("/doctor/queue", params={"department": "Panchakarma"}).json()
    general_queue = client.get("/doctor/queue").json()

    ky_ids = [q["session_id"] for q in ky_queue]
    pk_ids = [q["session_id"] for q in pk_queue]
    all_ids = [q["session_id"] for q in general_queue]

    # Kayachikitsa token only in Kayachikitsa queue
    assert ky_sid in ky_ids
    assert ky_sid not in pk_ids

    # Panchakarma token only in Panchakarma queue
    assert pk_sid in pk_ids
    assert pk_sid not in ky_ids

    # Safety case enters neither normal queue
    assert safe_sid not in ky_ids
    assert safe_sid not in pk_ids
    assert safe_sid not in all_ids

    # Safety case appears in emergency dashboard
    em_queue = client.get("/doctor/emergency").json()
    assert safe_sid in [e["session_id"] for e in em_queue]


# ==============================================================================
# INVARIANT 7: Doctor confirmation
# ==============================================================================
def test_invariant_7_doctor_confirmation_rules(client):
    # Non-flagged completed case can be confirmed
    sid = _start_consent_code(client, name="Safe Completed")
    _complete_interview(client, sid)
    client.post(f"/session/{sid}/documents-complete")
    client.post(f"/session/{sid}/token")

    r_confirm = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r_confirm.status_code == 200
    assert r_confirm.json()["doctor_review"]["confirmed"] is True

    # Flagged case CANNOT be confirmed
    safe_sid = _start_consent_code(client, name="Flagged Case")
    client.post(f"/session/{safe_sid}/answer", json={"answer": "difficulty breathing and chest pain"})

    r_forbidden_confirm = client.patch(f"/doctor/session/{safe_sid}", json={"doctor_confirmed": True})
    assert r_forbidden_confirm.status_code == 409
    assert "Cannot confirm a safety-flagged session" in r_forbidden_confirm.json()["detail"]


# ==============================================================================
# INVARIANT 8: No mutation on rejected requests
# ==============================================================================
def test_invariant_8_no_mutation_on_rejected_requests(client):
    # 1. Incomplete interview rejecting token does not mutate state
    sid = _start_consent_code(client)
    before = client.get(f"/session/{sid}").json()

    r1 = client.post(f"/session/{sid}/token")
    assert r1.status_code == 403

    after1 = client.get(f"/session/{sid}").json()
    assert before == after1

    # 2. Flagged session rejecting upload does not append any document
    client.post(f"/session/{sid}/answer", json={"answer": "severe chest pain"})
    before_flagged = client.get(f"/session/{sid}").json()

    r2 = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", PNG_FIXTURE.read_bytes(), "image/png")})
    assert r2.status_code == 403

    after2 = client.get(f"/session/{sid}").json()
    assert after2["documents"] == before_flagged["documents"]
    assert len(after2["documents"]) == 0

    # 3. Flagged session rejecting confirmation does not set doctor_confirmed or edited
    r3 = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r3.status_code == 409

    after3 = client.get(f"/session/{sid}").json()
    assert after3["doctor_review"]["confirmed"] is False
