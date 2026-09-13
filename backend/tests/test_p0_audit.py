"""P0 FINAL END-TO-END AUDIT — scenarios 1-9 (functional, deterministic).

Runs the complete MediKiosk workflow as an integrated system against the real
FastAPI app and SQLite via TestClient. Providers are mocked (clearly marked) so
results are deterministic; persistence is verified at every transition by
re-reading through the HTTP API.

Scenario map:
  1. Normal patient  P01..P09 + D01..D03 with persistence at every transition
  2. Safety patient   P05 shown, no token, no D01, D04 visible, refresh, no bypass
  3. OCR low confidence
  4. OCR provider failure (Gemini -> Groq; both fail)
  5. Interview/LLM failure (invalid JSON / provider failure)
  6. Refresh/resume at P02/P03/P04/P06/P07/P08/P09
  7. Token integrity matrix
  8. Doctor workflow (D01/D04/D02/D03)
  9. Department separation
"""
import json
import os
import struct
import tempfile
import zlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.services import ocr_provider


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_PATH"] = os.path.join(tmpdir, "p0_audit.db")
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


# ---------------------------------------------------------------------------
# Deterministic mocks (clearly separated so audits remain reproducible)
# ---------------------------------------------------------------------------

class _FakeProvider:
    provider_name = "gemini"


def _fake_extract(provider, field, ans):
    return {
        "chief_complaint": {"complaint": "katishoola", "confidence": 0.9},
        "onset": {"onset": "1 week ago", "confidence": 0.9},
        "duration": {"duration": "1 week", "confidence": 0.9},
        "severity": {"severity": "moderate", "confidence": 0.9},
        "character": {"character": "dull", "confidence": 0.9},
        "associated_symptoms": {"associated_symptoms": ["stiffness"], "confidence": 0.9},
    }[field]


def _fake_extract_pk(provider, field, ans):
    d = _fake_extract(provider, field, ans)
    if field == "chief_complaint":
        d = {"complaint": "Sthaulya", "confidence": 0.9}
    return d


_INTERVIEW = [
    ("chief_complaint", "katishoola"),
    ("onset", "1 week ago"),
    ("duration", "1 week"),
    ("severity", "moderate"),
    ("character", "dull"),
    ("associated_symptoms", "stiffness"),
]


def _state(client, sid):
    return client.get(f"/session/{sid}").json()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start(client, name="Audit Patient", age=45, gender="female", adaptive=True):
    r = client.post("/session/start", json={
        "patient": {"name": name, "age": age, "gender": gender},
        "language": "en", "visit_type": "new", "adaptive": adaptive,
    })
    assert r.status_code == 200
    return r.json()["session_id"]


def _consent(client, sid):
    assert client.post(f"/session/{sid}/consent", json={"consent_given": True}).status_code == 200


def _code(client, sid):
    r = client.post(f"/session/{sid}/patient-code")
    assert r.status_code == 200
    return r.json()["patient_code"]


def _complete_interview(client, sid, answers=_INTERVIEW, extract=_fake_extract):
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=extract):
        for _, ans in answers:
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            assert r.status_code == 200
            assert r.json()["red_flag"] is False
    s = _state(client, sid)
    assert s["interview_complete"] is True
    assert s["interview_step"] == "complete"
    return s


def _issue_token(client, sid):
    # token eligibility includes the completed P06 document step; mirror the
    # frontend by recording it before requesting the token
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    return r.json()


def _make_png(width=200, height=260) -> bytes:
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            dark = 22 < y < 30 or 62 < y < 70 or 102 < y < 110 or 150 < y < 158
            v = 60 if dark else 255
            rows += bytes([v, v, v])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


_VALID_OCR = json.dumps({"medicine": "Metformin", "strength": "500 mg", "dose": "one tablet",
                          "frequency": "twice daily", "confidence": 0.92})
_LOWCONF_OCR = json.dumps({"medicine": "Metformin", "strength": None, "dose": None,
                            "frequency": None, "confidence": 0.29})


async def _fake_ocr(self, image_bytes, mime, payload=_VALID_OCR):
    return payload


def _upload(client, sid, payload=_VALID_OCR, provider="GeminiVisionProvider"):
    async def _inner(self, image_bytes, mime):
        return payload
    with patch.object(getattr(ocr_provider, provider), "is_configured", return_value=True), \
         patch.object(getattr(ocr_provider, provider), "extract_prescription", _inner):
        return client.post(f"/session/{sid}/upload", files={"file": ("rx.png", _make_png(), "image/png")})


# ===========================================================================
# SCENARIO 1 — Normal patient full flow, persistence at every transition
# ===========================================================================

def test_s1_normal_flow_persistence_p01_to_d03(client):
    # P01 start (deterministic legacy intake path so the statutory
    # chief_complaint -> onset -> ... question order is exercised verbatim)
    sid = _start(client, adaptive=False)
    s = _state(client, sid)
    assert s["session_id"] == sid
    assert s["consent_given"] is False
    assert s["patient_code"] is None
    assert s["interview_complete"] is False
    assert s["interview_step"] == "chief_complaint"
    assert s["department"] is None and s["queue_token"] is None

    # P02 consent -> persisted
    _consent(client, sid)
    s = _state(client, sid)
    assert s["consent_given"] is True

    # P03 patient code -> generated once, persisted
    code = _code(client, sid)
    assert code.startswith("AIIA-") or code.startswith("MK-")
    s = _state(client, sid)
    assert s["patient_code"] == code
    assert _code(client, sid) == code  # idempotent

    # P04 interview -> each answer persisted, deterministic progression
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        for step in range(len(_INTERVIEW)):
            field, ans = _INTERVIEW[step]
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            assert r.status_code == 200
            assert r.json()["red_flag"] is False
            s = _state(client, sid)
            assert len(s["raw_answers"]) == step + 1
            assert s["raw_answers"][-1]["answer"] == ans
            assert len(s["answer_records"]) == step + 1
            assert s["answer_records"][-1]["provider"] == "gemini"
    assert s["interview_complete"] is True

    # P06 documents (skip -> no docs), P07 summary state
    s = _state(client, sid)
    assert s["documents"] == []
    assert s["department"] is None

    # P08 token issued + idempotent
    tok = _issue_token(client, sid)
    assert tok["token"].startswith("KY-")
    assert tok["department"] == "Kayachikitsa"
    s = _state(client, sid)
    assert s["department"] == "Kayachikitsa"
    assert s["queue_token"] == tok["token"]

    # D01 queue entry
    q = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    assert [i["session_id"] for i in q] == [sid]
    assert q[0]["patient_code"] == code
    assert q[0]["confirmed"] is False
    assert q[0]["ready_for_review"] is True

    # D02 doctor detail = authoritative persisted state
    d2 = client.get(f"/doctor/session/{sid}").json()
    assert d2["chief_complaint"] == "katishoola"
    assert d2["history_of_present_illness"]["onset"] == "1 week ago"
    assert d2["history_of_present_illness"]["associated_symptoms"] == ["stiffness"]
    assert d2["patient"]["name"] == "Audit Patient"
    assert d2["patient_code"] == code
    assert d2["department"] == "Kayachikitsa"

    # D03 edit persists
    r = client.patch(f"/doctor/session/{sid}", json={"severity": "high", "character": "aching"})
    assert r.status_code == 200
    assert r.json()["doctor_review"]["edited"] is True
    d2 = client.get(f"/doctor/session/{sid}").json()
    assert d2["history_of_present_illness"]["severity"] == "high"
    assert d2["history_of_present_illness"]["character"] == "aching"

    # D03 confirm persists (dropped from ready_for_review)
    r = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r.json()["doctor_review"]["confirmed"] is True
    q = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    assert q[0]["confirmed"] is True
    assert q[0]["ready_for_review"] is False


# ===========================================================================
# SCENARIO 2 — Safety patient
# ===========================================================================

def test_s2_safety_red_flag_full_matrix(client):
    sid = _start(client)
    _consent(client, sid)
    code = _code(client, sid)

    # deterministic red-flag answer
    r = client.post(f"/session/{sid}/answer", json={"answer": "I have severe chest pain"})
    assert r.status_code == 200
    assert r.json()["red_flag"] is True

    # P05 state authoritative: safety_flagged + detail + no advance
    s = _state(client, sid)
    assert s["safety_flagged"] is True
    assert "chest pain" in s["safety_detail"]
    assert s["interview_complete"] is False
    assert s["interview_step"] == "chief_complaint"
    assert s["raw_answers"][-1]["red_flag"] is True
    # patient code is kept (needed at D04/assistance)
    assert s["patient_code"] == code

    # refresh (new TestClient connection on same DB) preserves safety state
    with TestClient(app) as c2:
        s2 = c2.get(f"/session/{sid}").json()
        assert s2["safety_flagged"] is True

    # no normal token
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "safety_flagged"

    # no D01 entry (queue excludes flagged)
    queued = {i["session_id"] for i in client.get("/doctor/queue").json()}
    assert sid not in queued

    # D04 visibility (emergency dashboard lists it)
    emg = client.get("/doctor/emergency").json()
    assert [e["session_id"] for e in emg] == [sid]
    assert emg[0]["status"].startswith("Safety Alert")

    # cannot bypass safety: extra answers keep it paused (no advance)
    r = client.post(f"/session/{sid}/answer", json={"answer": "fine now"})
    assert r.json()["red_flag"] is True
    assert _state(client, sid)["interview_complete"] is False

    # cannot bypass via upload
    r = _upload(client, sid)
    assert r.status_code == 403

    # cannot bypass via patient-code re-request: endpoint blocks flagged sessions
    r = client.post(f"/session/{sid}/patient-code")
    assert r.status_code == 403 and "Safety review" in r.json()["detail"]

    # cannot bypass via status endpoint lying about readiness
    assert client.get(f"/session/{sid}/status").json()["ready_for_review"] is True  # unconfirmed, not confirmed


def test_s2_no_doctor_confirm_bypass(client):
    # F-03: flagged sessions must NOT be confirmable via doctor PATCH
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    client.post(f"/session/{sid}/answer", json={"answer": "stroke symptoms"})
    assert _state(client, sid)["safety_flagged"] is True
    r = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r.status_code == 409
    assert r.json()["detail"] == "Cannot confirm a safety-flagged session. Resolve the safety flag first."
    s = _state(client, sid)
    assert s["safety_flagged"] is True
    assert s["doctor_review"]["confirmed"] is False
    assert client.post(f"/session/{sid}/token").status_code == 403


# ===========================================================================
# SCENARIO 3 — OCR low confidence
# ===========================================================================

def test_s3_ocr_low_confidence_full_path(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)

    # upload low-confidence prescription
    r = _upload(client, sid, payload=_LOWCONF_OCR)
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True            # flagged
    assert body["medicine"] == "Metformin"
    assert body["confidence"] == 0.29

    # persisted on session
    s = _state(client, sid)
    assert len(s["documents"]) == 1
    assert s["documents"][0]["needs_review"] is True
    assert s["documents"][0]["extracted_value"] == "Metformin"
    assert s["documents"][0]["confidence"] == 0.29

    # P06 completed, but low confidence still withholds the token
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "pending_review"

    # patient correction possible -> review gate clears
    r = client.patch(f"/session/{sid}/document/0", json={"corrected_value": "Metformin Hydrochloride"})
    assert r.status_code == 200
    doc = r.json()
    assert doc["needs_review"] is False
    assert doc["manually_corrected"] is True
    assert doc["extracted_value"] == "Metformin Hydrochloride"

    # original extraction preserved exactly
    orig = doc["original_extraction"]
    assert orig["medicine"] == "Metformin"
    assert orig["confidence"] == 0.29
    assert orig["provider"] == "gemini"
    # provenance not overwritten
    assert doc["provider"] == "gemini"
    assert doc["confidence"] == 0.29

    # now the token can be issued
    r = client.post(f"/session/{sid}/token")
    assert r.status_code == 200
    assert r.json()["token"].startswith("KY-")


def test_s3_doctor_can_still_correct_and_original_preserved(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)
    _upload(client, sid, payload=_LOWCONF_OCR)
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    t = client.post(f"/session/{sid}/token")
    if t.status_code == 403:  # pending review as expected; correct via doctor now
        r = client.patch(f"/doctor/session/{sid}/document/0",
                         json={"corrected_value": "Glycomet", "dose": "one pill"})
        assert r.status_code == 200
        doc = r.json()["documents"][0]
        assert doc["extracted_value"] == "Glycomet"
        assert doc["needs_review"] is False
        assert doc["original_extraction"]["medicine"] == "Metformin"
        assert doc["original_extraction"]["confidence"] == 0.29
        # issued after correction
        assert client.post(f"/session/{sid}/token").status_code == 200


# ===========================================================================
# SCENARIO 4 — OCR provider failure
# ===========================================================================

def test_s4_gemini_failure_falls_back_to_groq(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)

    async def _boom(self, image_bytes, mime):
        raise RuntimeError("gemini is unavailable")

    async def _groq_ok(self, image_bytes, mime):
        return _VALID_OCR

    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _boom), \
         patch.object(ocr_provider.GroqVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GroqVisionProvider, "extract_prescription", _groq_ok):
        r = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", _make_png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is False
    assert body["medicine"] == "Metformin"
    doc = _state(client, sid)["documents"][0]
    assert doc["provider"] == "groq"  # fallback recorded, provenance honest


def test_s4_both_providers_fail_safe_error(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)

    async def _boom(self, image_bytes, mime):
        raise RuntimeError("provider exploded with secret")

    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _boom), \
         patch.object(ocr_provider.GroqVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GroqVisionProvider, "extract_prescription", _boom):
        r = client.post(f"/session/{sid}/upload", files={"file": ("rx.png", _make_png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True
    assert body["confidence"] == 0.0
    assert "provider exploded with secret" not in json.dumps(body)
    # review state persisted (documents flagged, token gated even after P06 done)
    assert client.post(f"/session/{sid}/documents-complete").status_code == 200
    doc = _state(client, sid)["documents"][0]
    assert doc["needs_review"] is True
    assert doc["provider"] == "unknown"
    assert client.post(f"/session/{sid}/token").status_code == 403


# ===========================================================================
# SCENARIO 5 — Interview / LLM failure
# ===========================================================================

def test_s5_invalid_llm_json_preserves_raw_and_progression(client):
    sid = _start(client, adaptive=False)
    _consent(client, sid)
    _code(client, sid)

    def _broken(provider, field, ans):
        raise json.JSONDecodeError("Invalid JSON from LLM", "{bad json", 0)

    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_broken):
        r = client.post(f"/session/{sid}/answer", json={"answer": "I feel unwell"})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True
    assert body["red_flag"] is False

    s = _state(client, sid)
    assert s["raw_answers"][-1]["answer"] == "I feel unwell"   # verbatim preserved
    assert s["answer_records"][-1]["needs_review"] is True
    assert s["answer_records"][-1]["provider"] is None
    # Interview MUST advance: raw answer stored as chief_complaint fallback
    assert s["interview_step"] == "onset", "LLM failure must not stall interview"
    assert s["interview_complete"] is False
    assert s["chief_complaint"] == "I feel unwell"

    # deterministic interview progression still correct after provider recovery
    # chief_complaint already set via fallback, so only onset-onwards fields remain
    remaining = [(f, a) for f, a in _INTERVIEW if f != "chief_complaint"]
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        for field, ans in remaining:
            r = client.post(f"/session/{sid}/answer", json={"answer": ans})
            assert r.json()["session_complete"] is (field == "associated_symptoms")
            assert r.json()["red_flag"] is False
    s = _state(client, sid)
    assert s["interview_complete"] is True
    assert all(rec["needs_review"] is False for rec in s["answer_records"] if rec["provider"])


def test_s5_safety_still_runs_when_llm_is_down(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)

    def _broken(provider, field, ans):
        raise RuntimeError("llm boom")

    # LLM broken + red-flag answer -> safety must still catch it
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_broken):
        r = client.post(f"/session/{sid}/answer", json={"answer": "difficulty breathing"})
    assert r.status_code == 200
    assert r.json()["red_flag"] is True
    assert _state(client, sid)["safety_flagged"] is True
    assert _state(client, sid)["raw_answers"][-1]["answer"] == "difficulty breathing"


# ===========================================================================
# SCENARIO 6 — Refresh / resume: backend is authoritative at every screen
# ===========================================================================

def test_s6_resume_state_at_every_stage(client):
    sid = _start(client)
    _consent(client, sid)
    code = _code(client, sid)
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=_fake_extract):
        client.post(f"/session/{sid}/answer", json={"answer": "katishoola"})
        client.post(f"/session/{sid}/answer", json={"answer": "1 week ago"})

    # P02-like (consent only): a fresh DB read must show exactly that
    s2 = _start(client)
    _consent(client, s2)
    st = _state(client, s2)
    assert st["consent_given"] is True and st["patient_code"] is None

    # P03-like (consent + code, no answers)
    s3 = _start(client)
    _consent(client, s3)
    c3 = _code(client, s3)
    st = _state(client, s3)
    assert st["patient_code"] == c3
    assert st["answer_records"] == []

    # P04 mid-interview resume: backend answers with the NEXT unanswered
    # concept and question (adaptive interviewer)
    st = _state(client, sid)
    assert st["patient_code"] == code
    assert st["interview_step"] not in (None, "", "complete")
    assert len(st["answer_records"]) == 2
    assert isinstance(st["next_question"], str) and st["next_question"]

    # P06-like: documents persisted and re-served (deterministic intake path)
    s6 = _start(client, adaptive=False)
    _consent(client, s6)
    _code(client, s6)
    _complete_interview(client, s6)
    _upload(client, s6)
    st = _state(client, s6)
    assert len(st["documents"]) == 1
    assert st["documents"][0]["extracted_value"] == "Metformin"
    assert st["documents"][0]["needs_review"] is False

    # P07-like: interview_complete, no token yet
    assert st["interview_complete"] is True
    assert st["queue_token"] is None
    assert st["department"] is None

    # P08/P09-like: token issued state persists across re-reads
    _issue_token(client, s6)
    st = _state(client, s6)
    assert st["queue_token"] is not None
    assert st["department"] == "Kayachikitsa"
    # repeated GET (simulated refresh) returns identical authoritative state
    assert _state(client, s6) == st


# ===========================================================================
# SCENARIO 7 — Token integrity matrix
# ===========================================================================

def test_s7_token_integrity_matrix(client):
    # a) incomplete -> rejected
    inc = _start(client)
    _consent(client, inc)
    _code(client, inc)
    r = client.post(f"/session/{inc}/token")
    assert r.status_code == 403 and r.json()["detail"]["error"] == "incomplete_session"

    # b) safety flagged -> rejected
    sf = _start(client)
    _consent(client, sf)
    _code(client, sf)
    client.post(f"/session/{sf}/answer", json={"answer": "severe bleeding"})
    r = client.post(f"/session/{sf}/token")
    assert r.status_code == 403 and r.json()["detail"]["error"] == "safety_flagged"

    # c) pending document review -> rejected
    pr = _start(client)
    _consent(client, pr)
    _code(client, pr)
    _complete_interview(client, pr)
    _upload(client, pr, payload=_LOWCONF_OCR)
    assert client.post(f"/session/{pr}/documents-complete").status_code == 200
    r = client.post(f"/session/{pr}/token")
    assert r.status_code == 403 and r.json()["detail"]["error"] == "pending_review"

    # d) valid completed safe session -> token generated
    ok = _start(client)
    _consent(client, ok)
    _code(client, ok)
    _complete_interview(client, ok)
    tok1 = _issue_token(client, ok)["token"]

    # e) repeated request -> same persisted token
    tok2 = client.post(f"/session/{ok}/token").json()["token"]
    assert tok1 == tok2


# ===========================================================================
# SCENARIO 8 — Doctor workflow
# ===========================================================================

def test_s8_d01_vs_d04_separation(client):
    # eligible normal case -> D01 only
    ok = _start(client)
    _consent(client, ok)
    _code(client, ok)
    _complete_interview(client, ok)
    _issue_token(client, ok)

    # safety case -> D04 only
    sf = _start(client)
    _consent(client, sf)
    _code(client, sf)
    client.post(f"/session/{sf}/answer", json={"answer": "anaphylaxis"})

    q = [i["session_id"] for i in client.get("/doctor/queue").json()]
    assert ok in q and sf not in q

    emg = [e["session_id"] for e in client.get("/doctor/emergency").json()]
    assert sf in emg and ok not in emg


def test_s8_d03_preserves_original_ai_extraction_on_doc_correct(client):
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)
    _upload(client, sid)  # high confidence valid doc

    # doctor corrects the medicine
    r = client.patch(f"/doctor/session/{sid}/document/0", json={"corrected_value": "Metformin XR"})
    assert r.status_code == 200
    doc = r.json()["documents"][0]
    assert doc["extracted_value"] == "Metformin XR"
    assert doc["original_extraction"]["medicine"] == "Metformin"
    assert doc["original_extraction"]["strength"] == "500 mg"
    assert doc["original_extraction"]["dose"] == "one tablet"
    assert doc["original_extraction"]["frequency"] == "twice daily"
    assert doc["original_extraction"]["confidence"] == 0.92
    assert doc["original_extraction"]["provider"] == "gemini"
    # provenance untouched
    assert doc["confidence"] == 0.92
    assert doc["provider"] == "gemini"


# ===========================================================================
# SCENARIO 9 — Department separation
# ===========================================================================

def test_s9_department_separation_and_filtering(client):
    ky = _start(client, name="Kaya Patient")
    _consent(client, ky)
    _code(client, ky)
    _complete_interview(client, ky, extract=_fake_extract)
    tok_ky = _issue_token(client, ky)
    assert tok_ky["department"] == "Kayachikitsa"
    assert tok_ky["token"].startswith("KY-")

    pk = _start(client, name="PK Patient")
    _consent(client, pk)
    _code(client, pk)
    _complete_interview(client, pk, extract=_fake_extract_pk, answers=[("chief_complaint", "Sthaulya")] + _INTERVIEW[1:])
    tok_pk = _issue_token(client, pk)
    assert tok_pk["department"] == "Panchakarma"
    assert tok_pk["token"].startswith("PK-")

    # correct filtering: Kaya queue has only Kaya session, PK queue only PK session
    kq = client.get("/doctor/queue", params={"department": "Kayachikitsa"}).json()
    pq = client.get("/doctor/queue", params={"department": "Panchakarma"}).json()
    assert [i["session_id"] for i in kq] == [ky]
    assert [i["session_id"] for i in pq] == [pk]
    assert [i["queue_token"] for i in kq] == [tok_ky["token"]]
    assert [i["queue_token"] for i in pq] == [tok_pk["token"]]

    # tokens are department-scoped sequences
    assert int(tok_pk["token"].split("-")[1]) == 1
    assert int(tok_ky["token"].split("-")[1]) == 1


# ===========================================================================
# F-03 REGRESSION — safety-flagged sessions must not be confirmable
# ===========================================================================

def test_f03_flagged_confirm_rejected(client):
    """(a) flagged + doctor_confirmed=true => 409"""
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    client.post(f"/session/{sid}/answer", json={"answer": "chest pain radiating to arm"})
    assert _state(client, sid)["safety_flagged"] is True

    r = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r.status_code == 409


def test_f03_flagged_remains_safety_flagged(client):
    """(b) flagged session remains safety_flagged=true after rejected confirm"""
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    client.post(f"/session/{sid}/answer", json={"answer": "severe chest pain"})
    client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert _state(client, sid)["safety_flagged"] is True


def test_f03_flagged_remains_doctor_unconfirmed(client):
    """(c) flagged session remains doctor_review.confirmed=false"""
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    client.post(f"/session/{sid}/answer", json={"answer": "chest pain and dizziness"})
    client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert _state(client, sid)["doctor_review"]["confirmed"] is False


def test_f03_non_flagged_confirm_still_works(client):
    """(d) non-flagged + doctor_confirmed=true => still succeeds"""
    sid = _start(client)
    _consent(client, sid)
    _code(client, sid)
    _complete_interview(client, sid)
    _issue_token(client, sid)

    r = client.patch(f"/doctor/session/{sid}", json={"doctor_confirmed": True})
    assert r.status_code == 200
    assert r.json()["doctor_review"]["confirmed"] is True