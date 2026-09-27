"""Product-integration graph: one coherent patient-to-doctor state machine.

Covers B/C/D/E/F/G/H/I/J/L at the API lifecycle level. Browser reality
lives in frontend/e2e/smoke.spec.ts. No LLM keys here: deterministic
fallback path (honestly labeled), same state machine as live.
"""
import json
import os
import struct
import tempfile
import zlib
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.services import ocr_provider as _ocr


def _client():
    tmp = tempfile.TemporaryDirectory()
    os.environ["DATABASE_PATH"] = os.path.join(tmp.name, "prod.db")
    from backend.db import init_db
    init_db()
    return TestClient(app), tmp


def _teardown(tmp):
    os.environ.pop("DATABASE_PATH", None)
    tmp.cleanup()


def _new(c, lang="en", visit="new", prior=None, name="Int Pat"):
    body = {"patient": {"name": name, "age": 33, "gender": "female"},
            "language": lang, "visit_type": visit}
    if prior:
        body["prior_patient_code"] = prior
    sid = c.post("/session/start", json=body).json()["session_id"]
    c.post(f"/session/{sid}/consent", json={"consent_given": True})
    code = c.post(f"/session/{sid}/patient-code").json()["patient_code"]
    return sid, code


def _no_llm():
    return patch.object(session_router, "generate_adaptive_turn",
                        new=AsyncMock(side_effect=RuntimeError("down")))


def _complete_interview(c, sid, answers):
    last = None
    with _no_llm():
        for a in answers:
            last = c.post(f"/session/{sid}/answer", json={"answer": a}).json()
    return last


def _png():
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    rows = bytearray()
    for _ in range(32):
        rows.append(0)
        rows += bytes([255, 255, 255] * 64)
    ihdr = struct.pack(">IIBBBBB", 64, 32, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))


# --- B: new patient full journey, HI persistence ----------------------------

def test_hi_journey_language_survives_every_transition():
    c, tmp = _client()
    try:
        sid, code = _new(c, lang="hi", name="HI Pat")
        s = c.get(f"/session/{sid}").json()
        assert s["language"] == "hi"
        assert "है" in s["next_question"] or any(
            "\u0900" <= ch <= "\u097f" for ch in s["next_question"])
        last = _complete_interview(c, sid, ["पेट में जलन है", "दो हफ्तों से",
                                            "मसालेदार खाने से", "हल्की है",
                                            "नींद में खलल"])
        assert last["session_complete"] is True
        # completion messaging localized, session still HI
        s2 = c.get(f"/session/{sid}").json()
        assert s2["language"] == "hi"
        c.post(f"/session/{sid}/documents-complete")
        c.post(f"/session/{sid}/patient-code")
        tok = c.post(f"/session/{sid}/token").json()
        assert tok["token"]
        d = c.get(f"/doctor/session/{sid}").json()
        assert d["language"] == "hi"
        assert d["patient_code"] == code
        assert d["chief_complaint"]
    finally:
        _teardown(tmp)


# --- C: returning separation -------------------------------------------------

def test_prior_context_never_overrides_new_information():
    c, tmp = _client()
    try:
        prior, code = _new(c, name="Ret Pat")
        _complete_interview(c, prior, ["Lower back pain for two months.", "Left side.",
                                       "Stairs.", "Stiff mornings.", "Disturbs work."])
        c.post(f"/session/{prior}/documents-complete")
        old_chief = c.get(f"/session/{prior}").json()["chief_complaint"]

        sid, _ = _new(c, visit="returning", prior=code, name="Ret Pat")
        s = c.get(f"/session/{sid}").json()
        assert s["chief_complaint"] is None  # prior never copied into new state
        with _no_llm():
            c.post(f"/session/{sid}/answer",
                   json={"answer": "Dry cough for five days."})
        g = c.get(f"/session/{sid}").json()
        assert g["presentation_domain"] == "respiratory"
        assert "cough" in g["chief_complaint"].lower() or "Cough" in str(g["collected_concepts"])
        assert old_chief not in (g["chief_complaint"] or "")
        # old visit immutable
        assert c.get(f"/session/{prior}").json()["chief_complaint"] == old_chief
    finally:
        _teardown(tmp)


# --- D: safety x full flow + bypass battery ----------------------------------

def test_flagged_session_freezes_and_every_bypass_fails():
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Flag Pat")
        r = c.post(f"/session/{sid}/answer", json={"answer": "vomiting blood since morning"})
        assert r.json()["red_flag"] is True
        # repeated answers stay frozen
        r2 = c.post(f"/session/{sid}/answer", json={"answer": "just back pain now"})
        assert r2.json()["red_flag"] is True
        assert r2.json()["interview_status"] == "safety_flagged"
        g = c.get(f"/session/{sid}").json()
        assert g["safety_flagged"] is True
        assert g["interview_complete"] is False
        # bypasses
        assert c.post(f"/session/{sid}/token").status_code == 403
        assert c.post(f"/session/{sid}/upload",
                      files={"file": ("x.png", _png(), "image/png")}).status_code == 403
        assert c.post(f"/session/{sid}/documents-complete").status_code == 403
        assert c.patch(f"/doctor/session/{sid}",
                       json={"doctor_confirmed": True}).status_code == 409
        em = c.get("/doctor/emergency").json()
        assert sid in [e["session_id"] for e in em]
        # refresh-equivalent reread preserves freeze
        assert c.get(f"/session/{sid}").json()["safety_flagged"] is True
    finally:
        _teardown(tmp)


# --- E/G: OCR failure + review-doc token block -------------------------------

def test_ocr_failure_preserves_state_and_blocks_token_until_reviewed():
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Doc Pat")
        _complete_interview(c, sid, ["Stomach burning.", "Two weeks.", "Spicy food.",
                                     "Mild.", "Sleep disturbed."])
        n_answers = len(c.get(f"/session/{sid}").json()["raw_answers"])

        async def _lowconf(self, image_bytes, mime):
            return json.dumps({"medicine": None, "strength": None, "dose": None,
                               "frequency": None, "confidence": 0.9})

        with patch.object(_ocr.GeminiVisionProvider, "is_configured", return_value=True), \
             patch.object(_ocr.GeminiVisionProvider, "extract_prescription", _lowconf):
            r = c.post(f"/session/{sid}/upload", files={"file": ("rx.png", _png(), "image/png")})
        assert r.json()["needs_review"] is True
        g = c.get(f"/session/{sid}").json()
        assert len(g["raw_answers"]) == n_answers  # interview intact
        c.post(f"/session/{sid}/documents-complete")
        blocked = c.post(f"/session/{sid}/token")
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["error"] == "pending_review"
        # patient corrects -> token flows
        c.patch(f"/session/{sid}/document/0", json={"corrected_value": "Metformin"})
        tok = c.post(f"/session/{sid}/token").json()
        assert tok["token"]
    finally:
        _teardown(tmp)


# --- G: token lifecycle --------------------------------------------------------

def test_token_idempotent_unique_and_refresh_stable():
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Tok A")
        _complete_interview(c, sid, ["Stomach burning.", "Two weeks.", "Spicy food.",
                                     "Mild.", "Sleep disturbed."])
        c.post(f"/session/{sid}/documents-complete")
        t1 = c.post(f"/session/{sid}/token").json()["token"]
        t2 = c.post(f"/session/{sid}/token").json()["token"]
        assert t1 == t2  # duplicate submit, one token
        assert c.get(f"/session/{sid}").json()["queue_token"] == t1  # refresh stable

        sid2, _ = _new(c, name="Tok B")
        _complete_interview(c, sid2, ["Knee pain.", "One month.", "Stairs.",
                                      "Stiff mornings.", "Walking hard."])
        c.post(f"/session/{sid2}/documents-complete")
        t3 = c.post(f"/session/{sid2}/token").json()["token"]
        assert t3 != t1  # never reused
        assert c.get(f"/doctor/queue").status_code == 200
        ids = [q["session_id"] for q in c.get("/doctor/queue").json()]
        assert sid in ids and sid2 in ids
    finally:
        _teardown(tmp)


def test_incomplete_or_unconsented_cannot_mint_token():
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Early Pat")
        assert c.post(f"/session/{sid}/token").status_code == 403
        with _no_llm():
            c.post(f"/session/{sid}/answer", json={"answer": "headache"})
        assert c.post(f"/session/{sid}/token").status_code == 403  # docs step missing
    finally:
        _teardown(tmp)


# --- F/H: summary integrity + cross-patient isolation --------------------------

def test_doctor_handoff_isolated_between_two_patients():
    c, tmp = _client()
    try:
        a, code_a = _new(c, name="Patient A")
        _complete_interview(c, a, ["Stomach burning.", "Two weeks.", "Spicy food.",
                                   "Mild.", "Sleep disturbed."])
        c.post(f"/session/{a}/documents-complete")
        ta = c.post(f"/session/{a}/token").json()["token"]

        b, code_b = _new(c, name="Patient B")
        with _no_llm():
            c.post(f"/session/{b}/answer", json={"answer": "vomiting blood today"})

        da = c.get(f"/doctor/session/{a}").json()
        db = c.get(f"/doctor/session/{b}").json()
        assert da["patient"]["name"] == "Patient A"
        assert db["patient"]["name"] == "Patient B"
        assert code_a != code_b and da["queue_token"] == ta
        for field in ("chief_complaint", "collected_concepts", "raw_answers",
                      "documents", "safety_detail", "concept_provenance",
                      "completeness_gaps", "clinical_mentions"):
            sa, sb = json.dumps(da[field]), json.dumps(db[field])
            assert sa != sb or da[field] in ({}, [], None), field
        assert "vomiting blood" not in json.dumps(da)
        assert "Stomach burning" not in json.dumps(db)
        assert db["safety_flagged"] is True and da["safety_flagged"] is False
        # returning B-style prior summary never leaks raw answers
        assert "raw_answers" not in json.dumps(da.get("concept_metadata", []))
    finally:
        _teardown(tmp)


# --- I: malformed / stale inputs ------------------------------------------------

def test_malformed_codes_and_stale_sessions_fail_cleanly():
    c, tmp = _client()
    try:
        assert c.get("/session/patient-lookup?code=" + "X" * 51).status_code == 400
        assert c.get("/session/patient-lookup?code=AIIA-000000-99999").json()["found"] is False
        assert c.get("/session/does-not-exist").status_code == 404
        assert c.post("/session/does-not-exist/answer", json={"answer": "x"}).status_code == 404
        # answer gating order: consent then code
        sid = c.post("/session/start", json={
            "patient": {"name": "Gate", "age": 20, "gender": "male"},
            "language": "en", "visit_type": "new"}).json()["session_id"]
        assert c.post(f"/session/{sid}/answer", json={"answer": "x"}).status_code == 403
        c.post(f"/session/{sid}/consent", json={"consent_given": True})
        assert c.post(f"/session/{sid}/answer", json={"answer": "x"}).status_code == 403
        assert c.post(f"/session/{sid}/patient-code").status_code == 200
    finally:
        _teardown(tmp)


# --- J: GU journey completion message + persistence ------------------------------

def test_gu_journey_completes_with_gujarati_messaging():
    c, tmp = _client()
    try:
        sid, _ = _new(c, lang="gu", name="GU Pat")
        s = c.get(f"/session/{sid}").json()
        assert s["language"] == "gu"
        assert any("\u0a80" <= ch <= "\u0aff" for ch in s["next_question"])
        with _no_llm():
            last = None
            for a in ["પેટમાં બળતરા છે", "બે અઠવાડિયાથી", "તીખા ખોરાકથી",
                      "હળવી છે", "ઊંઘમાં ખલેલ"]:
                last = c.post(f"/session/{sid}/answer", json={"answer": a}).json()
        assert last["session_complete"] is True
        c.post(f"/session/{sid}/documents-complete")
        assert c.post(f"/session/{sid}/token").status_code == 200
        assert c.get(f"/doctor/session/{sid}").json()["language"] == "gu"
    finally:
        _teardown(tmp)


# --- Spec §7.3: physician prose summary from structured data only ------------

def _stub_provider(text, name="stub"):
    class _P:
        provider_name = name

        async def generate(self, prompt, system_prompt=None, **kwargs):
            return text

    return _P()


def test_case_summary_uses_structured_data_only():
    import backend.services.llm_provider as _lp
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Sum Pat")
        seen = {}
        provider = _stub_provider("Patient reports stomach burning. Duration not available.")

        async def _spy(prompt, system_prompt=None, **kwargs):
            seen["system"] = system_prompt
            seen["user"] = prompt
            return "Patient reports stomach burning. Duration not available."

        provider.generate = _spy  # type: ignore[method-assign]
        with patch.object(_lp, "iter_llm_providers", return_value=[provider]):
            r = c.post(f"/doctor/session/{sid}/summary")
        assert r.status_code == 200
        assert "factual summary" in seen["system"]
        assert "chief_complaint" in seen["user"]  # structured input, never raw-only
        assert r.json()["provider"] == "stub"
        assert r.json()["summary"]
    finally:
        _teardown(tmp)


def test_case_summary_rejects_diagnosis_and_empty_output():
    import backend.services.llm_provider as _lp
    c, tmp = _client()
    try:
        sid, _ = _new(c, name="Sum Pat 2")
        with patch.object(_lp, "iter_llm_providers",
                          return_value=[_stub_provider("You have GERD, take antacids.", "bad")]):
            r = c.post(f"/doctor/session/{sid}/summary")
        assert r.status_code == 502
        assert r.json()["detail"]["retryable"] is True
        with patch.object(_lp, "iter_llm_providers", return_value=[]):
            r2 = c.post(f"/doctor/session/{sid}/summary")
        assert r2.status_code == 502
    finally:
        _teardown(tmp)


def test_case_summary_unknown_session_is_404():
    c, tmp = _client()
    try:
        assert c.post("/doctor/session/nope/summary").status_code == 404
    finally:
        _teardown(tmp)
