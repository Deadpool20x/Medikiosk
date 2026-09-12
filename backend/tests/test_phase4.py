import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.rules import department_rules
from backend.routers import session as session_router


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_phase4.db")
        os.environ["DATABASE_PATH"] = db_file
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


def _start(client):
    r = client.post("/session/start", json={
        "patient": {"name": "Phase4 Patient", "age": 40, "gender": "female"},
        "language": "en", "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def _complete_interview(client, sid, complaint="katishoola"):
    for ans in [complaint, "1 week ago", "1 week", "moderate", "dull", "stiffness"]:
        r = client.post(f"/session/{sid}/answer", json={"answer": ans})
    assert r.json()["session_complete"] is True


def _finish_docs(client, sid):
    r = client.post(f"/session/{sid}/documents-complete")
    assert r.status_code == 200, r.text


def test_token_403_incomplete_session(client):
    sid = _start(client)
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "incomplete_session"


def test_token_403_safety_flagged(client):
    sid = _start(client)
    client.post(f"/session/{sid}/answer", json={"answer": "I have severe chest pain"})
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    body = r.json()["detail"]
    assert body["error"] == "safety_flagged"


def test_token_403_pending_review(client):
    from backend.services import ocr_provider
    import json
    from pathlib import Path

    png = Path(__file__).resolve().parents[2].joinpath("frontend", "sample-prescription.png").read_bytes()

    async def _fake_ocr_unreadable(self, image_bytes, mime):
        return json.dumps({"medicine": None, "confidence": 0.9})

    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_unreadable):
        r = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", png, "image/png")})
        assert r.status_code == 200
        assert r.json()["needs_review"] is True
    _finish_docs(client, sid)
    r2 = client.post(f"/session/{sid}/token")
    assert r2.status_code == 403
    assert r2.json()["detail"]["error"] == "pending_review"


def test_token_issue_success_persisted_and_idempotent(client):
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    _finish_docs(client, sid)
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    body = r.json()
    assert body["token"].startswith("KY-")
    assert body["department"] == "Kayachikitsa"
    tok1 = body["token"]
    # idempotent repeat returns same token
    r2 = client.post(f"/session/{sid}/token")
    assert r2.json()["token"] == tok1
    # persisted on session response
    g = client.get(f"/session/{sid}").json()
    assert g["queue_token"] == tok1
    assert g["department"] == "Kayachikitsa"


def test_token_sequential_per_department(client):
    first = client.post("/session/start", json={"patient": {"name": "A", "age": 30, "gender": "m"}}).json()["session_id"]
    client.post(f"/session/{first}/consent", json={"consent_given": True})
    client.post(f"/session/{first}/patient-code")
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, first)
    _finish_docs(client, first)
    t1 = client.post(f"/session/{first}/token").json()["token"]

    second = client.post("/session/start", json={"patient": {"name": "B", "age": 31, "gender": "f"}}).json()["session_id"]
    client.post(f"/session/{second}/consent", json={"consent_given": True})
    client.post(f"/session/{second}/patient-code")
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, second)
    _finish_docs(client, second)
    t2 = client.post(f"/session/{second}/token").json()["token"]

    assert int(t1.split("-")[1]) + 1 == int(t2.split("-")[1])


def test_department_routing_panchakarma(client):
    sid = _start(client)
    def _fake_extract_pk_case(ans, current_concept=None, domain_hint=None):
        d = _fake_extract_case(ans, current_concept, domain_hint)
        if current_concept == "primary_symptom":
            d["concepts"]["primary_symptom"] = "Sthaulya"
        return d
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_pk_case):
        for ans in ["Sthaulya", "1 week ago", "1 week", "moderate", "dull", "stiffness"]:
            client.post(f"/session/{sid}/answer", json={"answer": ans})
    _finish_docs(client, sid)
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    assert r.json()["department"] == "Panchakarma"
    assert r.json()["token"].startswith("PK-")


def test_department_classifier_deterministic():
    from backend.models.schema import Session, Patient, HistoryOfPresentIllness
    s = Session(session_id="x", patient=Patient(name="n", age=1, gender="m"))
    s.history_of_present_illness = HistoryOfPresentIllness()
    s.chief_complaint = "stiff knees Sandhivata"
    assert department_rules.classify_department(s) == "Kayachikitsa"

    s2 = Session(session_id="y", patient=Patient(name="n", age=1, gender="m"))
    s2.chief_complaint = "Sthaulya"
    assert department_rules.classify_department(s2) == "Panchakarma"


def test_d01_queue_excludes_non_queued_and_flagged(client):
    flagged = _start(client)
    client.post(f"/session/{flagged}/answer", json={"answer": "chest pain"})

    safe = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, safe)
    _finish_docs(client, safe)
    client.post(f"/session/{safe}/token")

    queued = client.get("/doctor/queue").json()
    ids = {q["session_id"] for q in queued}
    assert safe in ids
    assert flagged not in ids


def test_d01_department_filter_and_status(client):
    ky = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, ky)
    _finish_docs(client, ky)
    client.post(f"/session/{ky}/token")

    pk = _start(client)
    def _fake_extract_pk_case(ans, current_concept=None, domain_hint=None):
        d = _fake_extract_case(ans, current_concept, domain_hint)
        if current_concept == "primary_symptom":
            d["concepts"]["primary_symptom"] = "Sthaulya"
        return d
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_pk_case):
        for ans in ["Sthaulya", "1 week ago", "1 week", "moderate", "dull", "stiffness"]:
            client.post(f"/session/{pk}/answer", json={"answer": ans})
    _finish_docs(client, pk)
    client.post(f"/session/{pk}/token")

    kq = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    pq = client.get("/doctor/queue", params={"department": "Panchakarma"}).json()
    assert [q["session_id"] for q in kq] == [ky]
    assert [q["session_id"] for q in pq] == [pk]
    item = kq[0]
    assert item["patient_code"]
    assert item["queue_token"].startswith("KY-")
    assert item["ready_for_review"] is True
    assert item["confirmed"] is False


def test_d02_doctor_session_detail(client):
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    _finish_docs(client, sid)
    client.post(f"/session/{sid}/token")
    g = client.get(f"/doctor/session/{sid}")
    assert g.status_code == 200
    body = g.json()
    assert body["chief_complaint"] == "katishoola"
    assert body["history_of_present_illness"]["onset"] == "1 week ago"
    assert body["department"] == "Kayachikitsa"
    assert body["queue_token"].startswith("KY-")


def test_d03_doctor_edit_persists_and_marks_edited(client):
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    _finish_docs(client, sid)
    client.post(f"/session/{sid}/token")

    r = client.patch(f"/doctor/session/{sid}", json={
        "chief_complaint": "knee pain (lower back)",
        "severity": "high",
        "character": "aching",
    })
    assert r.status_code == 200
    assert r.json()["doctor_review"]["edited"] is True
    assert r.json()["chief_complaint"] == "knee pain (lower back)"
    assert r.json()["history_of_present_illness"]["severity"] == "high"

    g = client.get(f"/doctor/session/{sid}").json()
    assert g["chief_complaint"] == "knee pain (lower back)"
    assert g["doctor_review"]["edited"] is True


def test_d03_doctor_confirm_case(client):
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    _finish_docs(client, sid)
    client.post(f"/session/{sid}/token")

    r = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r.json()["doctor_review"]["confirmed"] is True

    # confirmed session is no longer ready_for_review in the queue
    q = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    item = [x for x in q if x["session_id"] == sid][0]
    assert item["confirmed"] is True
    assert item["ready_for_review"] is False


def test_refresh_resume_returns_token_and_department(client):
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    _finish_docs(client, sid)
    token = client.post(f"/session/{sid}/token").json()["token"]
    # simulated refresh after token issued
    g = client.get(f"/session/{sid}").json()
    assert g["queue_token"] == token
    assert g["department"] == "Kayachikitsa"


def test_no_fake_queue_stats_without_token(client):
    # sessions completed but never issued a token must NOT appear in queue
    sid = _start(client)
    with patch.object(session_router, "extract_case", side_effect=_fake_extract_case):
        _complete_interview(client, sid)
    q = client.get("/doctor/queue").json()
    assert sid not in {x["session_id"] for x in q}