"""Graphs E/F/G/H: completeness gaps, provenance, OCR merge policy,
obsolete prior context, ambiguity/contradiction/hallucination handling.

Architecture invariant: the LLM interviews; deterministic code verifies.
"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import session as session_router
from backend.rules.adaptive_interview import (
    DOMAIN_DIGESTIVE,
    completeness_gaps,
    extract_concepts_from_text,
    classify_presentation_domain,
)


def _ns(**kw):
    base = dict(presentation_domain=DOMAIN_DIGESTIVE, collected_concepts={},
                asked_concepts=[], asked_questions=[], adaptive_question_count=0,
                denied_concepts=[], language="en")
    base.update(kw)
    return SimpleNamespace(**base)


# --- Graph E: required info constrains completeness, not order -------------

def test_gaps_list_required_digestive_concepts_initially():
    gaps = completeness_gaps(_ns())
    required = {g["concept"] for g in gaps if g["required"]}
    assert {"primary_symptom", "duration", "food_relationship"} <= required


def test_gaps_shrink_as_facts_arrive_without_any_order():
    s = _ns(collected_concepts={"food_relationship": "spicy food", "duration": "two weeks"})
    gaps = completeness_gaps(s)
    required = {g["concept"] for g in gaps if g["required"]}
    assert "food_relationship" not in required and "duration" not in required
    assert "primary_symptom" in required


def test_denied_concept_is_not_a_gap():
    s = _ns(collected_concepts={"primary_symptom": "burning", "duration": "2 wks",
                                "food_relationship": "spicy"},
            denied_concepts=["fever"])
    gaps = completeness_gaps(s)
    assert not any(g["concept"] in ("associated_symptoms",) and g["required"] for g in gaps)


# --- Graph F: provenance ----------------------------------------------------

def _client():
    tmp = tempfile.TemporaryDirectory()
    os.environ["DATABASE_PATH"] = os.path.join(tmp.name, "prov.db")
    from backend.db import init_db
    init_db()
    return TestClient(app), tmp


def _start_consent_code(c):
    sid = c.post("/session/start", json={
        "patient": {"name": "P", "age": 30, "gender": "male"},
        "language": "en", "visit_type": "new"}).json()["session_id"]
    c.post(f"/session/{sid}/consent", json={"consent_given": True})
    c.post(f"/session/{sid}/patient-code")
    return sid


def _llm(concepts, text="Q?", target="duration", provider="stub"):
    return {"case_update": {"presentation": "digestive", "concepts": concepts,
                            "denied_concepts": [], "mentioned_documents": []},
            "next_question": {"text": text, "target_concept": target,
                              "reason": "r", "priority": "normal"},
            "status": "continue", "confidence": 0.9, "provider": provider}


def test_provenance_labels_llm_vs_heuristic():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(return_value=_llm(
                              {"severity": "severe"},
                              "How long have you noticed this?", "duration"))):
            c.post(f"/session/{sid}/answer",
                   json={"answer": "My stomach is burning severely."})
        g = c.get(f"/session/{sid}").json()
        prov = g["concept_provenance"]
        assert prov["severity"] == {"source": "llm", "provider": "stub"}
        # heuristic-only concept labeled as such (site=stomach not in LLM concepts)
        assert prov["site"] == {"source": "heuristic", "provider": None}
        assert g["collected_concepts"].get("primary_symptom") == "burning sensation in the stomach"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_failure_path_provenance_is_patient_raw_and_reviewed():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer", json={"answer": "my pain started yesterday"})
        g = c.get(f"/session/{sid}").json()
        assert g["concept_provenance"]["primary_symptom"]["source"] == "patient_raw"
        assert g["answer_records"][-1]["needs_review"] is True
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_doctor_patch_marks_clinician_entered():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer", json={"answer": "stomach pain"})
        d = c.patch(f"/doctor/session/{sid}", json={"duration": "3 days"}).json()
        assert d["concept_provenance"]["duration"] == {"source": "clinician-entered", "provider": None}
        assert d["doctor_review"]["edited"] is True
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_api_multi_fact_closes_gaps():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            r = c.post(f"/session/{sid}/answer", json={
                "answer": "I have burning for two weeks, it is mild, and spicy food makes it worse."})
        assert r.status_code == 200
        g = c.get(f"/session/{sid}").json()
        required = {x["concept"] for x in g["completeness_gaps"] if x["required"]}
        assert "duration" not in required  # satisfied by the single multi-fact answer
        assert "food_relationship" not in required
        assert g["collected_concepts"]["food_relationship"] == "spicy food"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_doctor_view_includes_gaps_and_provenance():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer", json={"answer": "stomach burning"})
        d = c.get(f"/doctor/session/{sid}").json()
        assert isinstance(d["completeness_gaps"], list)
        assert "primary_symptom" in d["concept_provenance"]
        # raw wording preserved for the doctor
        assert d["raw_answers"][0]["answer"] == "stomach burning"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


# --- Graph G: OCR merge policy ----------------------------------------------

def _make_png():
    import struct
    import zlib

    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    w, h = 64, 32
    rows = bytearray()
    for _ in range(h):
        rows.append(0)
        rows += bytes([255, 255, 255] * w)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))


def test_ocr_and_verbal_information_coexist_without_overwrite():
    """OCR output lands in documents[] with provider provenance; it never
    overwrites patient-entered HPI/chief complaint. Verbal + OCR coexist."""
    import json as _json
    from unittest.mock import patch as _patch
    from backend.services import ocr_provider as _ocr

    async def _fake(self, image_bytes, mime):
        return _json.dumps({"medicine": "Metformin", "strength": "500 mg",
                            "dose": "one tablet", "frequency": "twice daily",
                            "confidence": 0.92})

    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with _patch.object(_ocr.GeminiVisionProvider, "is_configured", return_value=True), \
             _patch.object(_ocr.GeminiVisionProvider, "extract_prescription", _fake):
            r = c.post(f"/session/{sid}/upload",
                       files={"file": ("rx.png", _make_png(), "image/png")})
        assert r.status_code == 200
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer",
                   json={"answer": "I take paracetamol when the stomach pain is bad."})
        g = c.get(f"/session/{sid}").json()
        assert g["documents"][0]["extracted_value"] == "Metformin"
        assert g["documents"][0]["provider"] in ("gemini", "groq", "unknown")
        # OCR never touched interview state
        assert "Metformin" not in _json.dumps(g["collected_concepts"])
        assert g["chief_complaint"] != "Metformin"
        # verbal mention preserved verbatim
        assert "paracetamol" in g["raw_answers"][-1]["answer"]
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()

# --- Graph H: adversarial ---------------------------------------------------
# Governance subset: patient disease-term use, LLM label inference attempts.

def test_patient_disease_term_preserved_without_system_assertion():
    """Patient says 'I have amlapitta': raw meaning preserved, domain routes
    on the trigger, but the system never echoes it as a diagnosis and the
    mention is flagged provisional for the doctor."""
    from backend.rules.clinical_review import CONTESTED_CORRELATES
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            r = c.post(f"/session/{sid}/answer",
                       json={"answer": "I have amlapitta, with burning after meals."})
        assert r.status_code == 200
        assert r.json()["red_flag"] is False
        g = c.get(f"/session/{sid}").json()
        assert g["presentation_domain"] == "digestive"
        assert g["raw_answers"][-1]["answer"] == "I have amlapitta, with burning after meals."
        q = (g["next_question"] or "").lower()
        assert not any(cor in q for cor in CONTESTED_CORRELATES)
        mentions = {m["term"].lower(): m["status"] for m in g["clinical_mentions"]}
        assert mentions.get("amlapitta") == "provisional"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_llm_contested_label_proposal_rejected_to_fallback():
    """LLM tries 'Do you have amlapitta?' -> validator blocks -> deterministic
    fallback question, honestly labeled, with no contested label shown."""
    from backend.rules.clinical_review import CONTESTED_CORRELATES
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(return_value=_llm(
                              {}, "Do you have amlapitta after meals?",
                              "food_relationship"))), \
             patch.object(session_router, "correct_adaptive_turn",
                          new=AsyncMock(return_value=None)):
            r = c.post(f"/session/{sid}/answer",
                       json={"answer": "My stomach burns after eating."})
        assert r.status_code == 200
        assert r.json()["question_source"] == "fallback_generated"
        q = (r.json()["next_question"] or "").lower()
        assert not any(cor in q for cor in CONTESTED_CORRELATES)
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_returning_conflict_applies_richer_update_with_provenance():
    """Old prior 'two months' vs new 'started only yesterday': the richer
    update wins, provenance is kept, nothing is silently merged."""
    c, tmp = _client()
    try:
        prior = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "new"}).json()["session_id"]
        c.post(f"/session/{prior}/consent", json={"consent_given": True})
        code = c.post(f"/session/{prior}/patient-code").json()["patient_code"]
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            for a in ["Lower back pain for two months.", "Left side.", "Stairs.",
                      "Stiff mornings.", "Disturbs work."]:
                c.post(f"/session/{prior}/answer", json={"answer": a})
            c.post(f"/session/{prior}/documents-complete")
        sid = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "returning",
            "prior_patient_code": code}).json()["session_id"]
        c.post(f"/session/{sid}/consent", json={"consent_given": True})
        c.post(f"/session/{sid}/patient-code")
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer",
                   json={"answer": "This episode started yesterday and has been going on for two days."})
        g = c.get(f"/session/{sid}").json()
        assert g["collected_concepts"]["onset"] == "yesterday"
        assert g["collected_concepts"]["duration"] == "two days"
        assert "duration" in g["concept_provenance"]
        # prior visit untouched
        from backend.db import get_session as _get
        import os as _os
        old = _get(prior, db_path=_os.environ.get("DATABASE_PATH"))
        assert old.collected_concepts.get("duration") == "two months"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_ambiguous_ayurvedic_term_is_not_forced():
    # "vata" alone must not hijack domain or concepts; raw preserved by caller.
    assert classify_presentation_domain("my vata is imbalanced, I feel uneasy") == "general"
    assert extract_concepts_from_text("my vata is imbalanced") == {}


def test_mixed_language_input_routes_correctly():
    assert classify_presentation_domain("मुझे knee में दर्द है") == "musculoskeletal"
    assert extract_concepts_from_text("मुझे knee में दर्द है")["site"] == "knee"


def test_contradictory_answer_purges_llm_hallucination():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(return_value=_llm(
                              {"associated_symptoms": "feverish feeling"},
                              "Do you have fever?", "associated_symptoms"))):
            r = c.post(f"/session/{sid}/answer",
                       json={"answer": "My stomach burns but I have no fever."})
        assert r.status_code == 200
        g = c.get(f"/session/{sid}").json()
        assert "fever" not in str(g["collected_concepts"].get("associated_symptoms", "")).lower()
        assert g["answer_records"][-1]["needs_review"] is True
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_anatomical_hallucination_is_purged():
    c, tmp = _client()
    try:
        sid = _start_consent_code(c)
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(return_value=_llm(
                              {"site": "jaw pain"},
                              "Tell me about your jaw?", "site"))):
            r = c.post(f"/session/{sid}/answer", json={"answer": "My stomach burns."})
        g = c.get(f"/session/{sid}").json()
        assert "jaw" not in str(g["collected_concepts"].get("site", "")).lower()
        assert g["answer_records"][-1]["needs_review"] is True
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_obsolete_prior_context_is_overridden_by_new_complaint():
    c, tmp = _client()
    try:
        # prior completed MSK visit
        prior = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "new"}).json()["session_id"]
        c.post(f"/session/{prior}/consent", json={"consent_given": True})
        code = c.post(f"/session/{prior}/patient-code").json()["patient_code"]
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            for a in ["Lower back pain for two months.", "Left side.", "Stairs.",
                      "Stiff mornings.", "Disturbs work."]:
                c.post(f"/session/{prior}/answer", json={"answer": a})
            c.post(f"/session/{prior}/documents-complete")
        # new visit, unrelated respiratory complaint
        new = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "returning",
            "prior_patient_code": code}).json()
        assert new["prior_context_loaded"] is True
        sid = new["session_id"]
        c.post(f"/session/{sid}/consent", json={"consent_given": True})
        c.post(f"/session/{sid}/patient-code")
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer",
                   json={"answer": "I have had a dry cough for five days."})
        g = c.get(f"/session/{sid}").json()
        assert g["presentation_domain"] == "respiratory"
        assert g["collected_concepts"]["cough_character"] == "dry cough"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()


def test_relevant_new_complaint_keeps_prior_domain():
    # Follow-up on the SAME problem must not re-route (no false override).
    c, tmp = _client()
    try:
        prior = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "new"}).json()["session_id"]
        c.post(f"/session/{prior}/consent", json={"consent_given": True})
        code = c.post(f"/session/{prior}/patient-code").json()["patient_code"]
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            for a in ["Lower back pain for two months.", "Left side.", "Stairs.",
                      "Stiff mornings.", "Disturbs work."]:
                c.post(f"/session/{prior}/answer", json={"answer": a})
            c.post(f"/session/{prior}/documents-complete")
        sid = c.post("/session/start", json={
            "patient": {"name": "R", "age": 40, "gender": "male"},
            "language": "en", "visit_type": "returning",
            "prior_patient_code": code}).json()["session_id"]
        c.post(f"/session/{sid}/consent", json={"consent_given": True})
        c.post(f"/session/{sid}/patient-code")
        with patch.object(session_router, "generate_adaptive_turn",
                          new=AsyncMock(side_effect=RuntimeError("down"))):
            c.post(f"/session/{sid}/answer",
                   json={"answer": "The back pain became much worse this week."})
        g = c.get(f"/session/{sid}").json()
        assert g["presentation_domain"] == "musculoskeletal"
    finally:
        os.environ.pop("DATABASE_PATH", None)
        tmp.cleanup()
