import json
import os
import struct
import tempfile
import zlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ocr_provider


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_PATH"] = os.path.join(tmpdir, "test_ocr.db")
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def _make_png(width=200, height=260) -> bytes:
    """Synthetic, valid PNG 'prescription' — white page with text-like bands."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter: None
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


def _start_and_code(client):
    r = client.post("/session/start", json={
        "patient": {"name": "OCR Test", "age": 40, "gender": "female"},
        "language": "en", "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


_VALID_PAYLOAD = json.dumps({
    "medicine": "Metformin", "strength": "500 mg", "dose": "one tablet",
    "frequency": "twice daily", "confidence": 0.92,
})

async def _fake_ocr_success(self, image_bytes, mime):
    return _VALID_PAYLOAD

async def _fake_ocr_lowconf(self, image_bytes, mime):
    return json.dumps({"medicine": "Metformin", "strength": None, "dose": None,
                       "frequency": None, "confidence": 0.3})

async def _fake_ocr_unreadable(self, image_bytes, mime):
    return json.dumps({"medicine": None, "strength": None, "dose": None,
                       "frequency": None, "confidence": 0.9})

async def _fake_ocr_malformed(self, image_bytes, mime):
    return "this is not json"

async def _fake_ocr_extra_keys(self, image_bytes, mime):
    return json.dumps({"medicine": "Metformin", "confidence": 0.9, "diagnosis": "banana"})

def _upload(client, sid, data, filename="prescription.png", mime="image/png"):
    return client.post(f"/session/{sid}/upload", files={"file": (filename, data, mime)})


def test_valid_prescription_image(client):
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_success):
        r = _upload(client, sid, _make_png())
    body = r.json()
    assert r.status_code == 200
    assert body["needs_review"] is False
    assert body["confidence"] == 0.92
    assert body["medicine"] == "Metformin"
    assert body["strength"] == "500 mg"
    assert body["dose"] == "one tablet"
    assert body["frequency"] == "twice daily"


def test_low_confidence_extraction_flagged_for_review(client):
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_lowconf):
        r = _upload(client, sid, _make_png())
    assert r.status_code == 200
    assert r.json()["needs_review"] is True
    assert r.json()["confidence"] == 0.3


def test_unreadable_medicine_is_review_not_invention(client):
    # medicine=None with HIGH confidence: still needs_review and never guessed
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_unreadable):
        _upload(client, sid, _make_png())
    doc = client.get(f"/session/{sid}").json()["documents"][0]
    assert doc["extracted_value"] is None
    assert doc["needs_review"] is True


def test_invalid_file_type_rejected(client):
    sid = _start_and_code(client)
    r = _upload(client, sid, b"not an image", filename="notes.txt", mime="text/plain")
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_forged_mime_rejected_by_magic_bytes(client):
    # claims to be PNG but is not an image
    sid = _start_and_code(client)
    r = _upload(client, sid, b"this is text pretending", filename="fake.png", mime="image/png")
    assert r.status_code == 400


def test_oversized_file_rejected(client):
    sid = _start_and_code(client)
    # valid PNG magic bytes but payload exceeds the 8 MB upload cap
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (8 * 1024 * 1024)
    r = _upload(client, sid, big)
    assert r.status_code == 413
    assert "too large" in r.json()["detail"]


def test_malformed_provider_json_is_review_and_no_crash(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_malformed):
        r = _upload(client, sid, _make_png())
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True
    # never expose raw provider output to the patient
    assert "this is not json" not in json.dumps(body)


def test_unexpected_fields_rejected(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    # provider returns an extra field -> schema gate rejects it -> needs_review
    from backend.rules import safety_rules  # noqa
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_extra_keys):
        r = _upload(client, sid, _make_png())
    assert r.status_code == 200
    assert r.json()["needs_review"] is True


def test_gemini_failure_falls_back_to_groq(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    async def _boom(self, image_bytes, mime):
        raise RuntimeError("gemini down")
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _boom), \
         patch.object(ocr_provider.GroqVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GroqVisionProvider, "extract_prescription", _fake_ocr_success):
        r = _upload(client, sid, _make_png())
    body = r.json()
    assert r.status_code == 200
    assert body["needs_review"] is False
    assert body["medicine"] == "Metformin"
    doc = client.get(f"/session/{sid}").json()["documents"][0]
    assert doc["provider"] == "groq"


def test_both_providers_fail_returns_review_no_error_leak(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    async def _boom(self, image_bytes, mime):
        raise RuntimeError("provider exploded")
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _boom), \
         patch.object(ocr_provider.GroqVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GroqVisionProvider, "extract_prescription", _boom):
        r = _upload(client, sid, _make_png())
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True
    assert body["confidence"] == 0.0
    serialized = json.dumps(body)
    assert "provider exploded" not in serialized
    assert "stack" not in serialized


def test_confidence_threshold_boundary(client):
    def _fake_confidence(of):
        async def _inner(self, image_bytes, mime):
            return json.dumps({"medicine": "Amlodipine", "strength": None, "dose": None,
                               "frequency": None, "confidence": of})
        return _inner
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_confidence(0.49)):
        r1 = _upload(client, sid, _make_png())
    assert r1.json()["needs_review"] is True
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_confidence(0.5)):
        r2 = _upload(client, sid, _make_png())
    assert r2.json()["needs_review"] is False


def test_manual_correction_preserves_original_ai_value(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_success):
        _upload(client, sid, _make_png())
    r = client.patch(f"/session/{sid}/document/0", json={
        "corrected_value": "Metformin Hydrochloride", "dose": "one pill",
    })
    assert r.status_code == 200
    doc = r.json()
    assert doc["extracted_value"] == "Metformin Hydrochloride"
    assert doc["manually_corrected"] is True
    assert doc["needs_review"] is False  # manual correction clears the review gate
    assert doc["original_extraction"]["medicine"] == "Metformin"
    assert doc["original_extraction"]["dose"] == "one tablet"
    assert doc["original_extraction"]["confidence"] == 0.92
    assert doc["original_extraction"]["provider"] == "gemini"
    # provenance intact
    assert doc["provider"] == "gemini"
    assert doc["confidence"] == 0.92
    assert doc["raw_result"] is not None


def test_document_persistence_and_reload(client):
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_success):
        _upload(client, sid, _make_png())
    client.patch(f"/session/{sid}/document/0", json={"corrected_value": "Metformin XR"})
    # reload from disk storage through get_session
    from backend.db import get_session
    reloaded = get_session(sid)
    assert len(reloaded.documents) == 1
    assert reloaded.documents[0].extracted_value == "Metformin XR"
    assert reloaded.documents[0].original_extraction["medicine"] == "Metformin"
    assert reloaded.documents[0].provider == "gemini"


def test_multiple_documents_appended(client):
    from backend.services import ocr_provider
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_success):
        _upload(client, sid, _make_png())
        _upload(client, sid, _make_png())
    docs = client.get(f"/session/{sid}").json()["documents"]
    assert len(docs) == 2
    assert docs[0]["extracted_value"] == docs[1]["extracted_value"] == "Metformin"


def test_flagged_session_cannot_bypass_safety_via_upload(client):
    sid = _start_and_code(client)
    client.post(f"/session/{sid}/answer", json={"answer": "severe chest pain"})
    assert client.get(f"/session/{sid}").json()["safety_flagged"] is True
    from backend.rules import safety_rules  # noqa
    from backend.services import ocr_provider
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr_success):
        r = _upload(client, sid, _make_png())
    assert r.status_code == 403
    assert "Safety review required" in r.json()["detail"]


def test_upload_requires_consent_and_patient_code(client):
    r = client.post("/session/start", json={
        "patient": {"name": "X", "age": 30, "gender": "m"},
    })
    sid = r.json()["session_id"]
    r1 = _upload(client, sid, _make_png())
    assert r1.status_code == 403  # no consent
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    r2 = _upload(client, sid, _make_png())
    assert r2.status_code == 403  # no patient code