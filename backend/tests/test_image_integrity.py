import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ocr_provider

ROOT = Path(__file__).resolve().parents[2]
PNG_FIXTURE = ROOT / "frontend" / "sample-prescription.png"
JPG_FIXTURE = ROOT / "frontend" / "sample-prescription.jpg"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_PATH"] = os.path.join(tmpdir, "test_integrity.db")
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


async def _fake_ocr(self, image_bytes, mime):
    return ('{"medicine": "Metformin", "strength": "500 mg", "dose": "One tablet", '
            '"frequency": "Twice daily", "confidence": 0.9}')


def _start_and_code(client):
    r = client.post("/session/start", json={
        "patient": {"name": "Integrity Test", "age": 40, "gender": "female"},
        "language": "en", "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def _upload(client, sid, data, filename="rx.png", mime="image/png"):
    return client.post(f"/session/{sid}/upload", files={"file": (filename, data, mime)})


def _ok_upload(client, sid, data, filename, mime):
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr):
        return _upload(client, sid, data, filename, mime)


def test_valid_png_fixture_accepted(client):
    sid = _start_and_code(client)
    r = _ok_upload(client, sid, PNG_FIXTURE.read_bytes(), "rx.png", "image/png")
    assert r.status_code == 200
    assert r.json()["medicine"] == "Metformin"
    assert r.json()["needs_review"] is False


def test_valid_jpeg_fixture_accepted(client):
    sid = _start_and_code(client)
    r = _ok_upload(client, sid, JPG_FIXTURE.read_bytes(), "rx.jpg", "image/jpeg")
    assert r.status_code == 200
    assert r.json()["medicine"] == "Metformin"
    assert r.json()["needs_review"] is False


@pytest.mark.parametrize("payload", [
    b"",
    b"not an image",
    b"\x00\x01\x02\x03random",
    PNG_MAGIC + b"\x00" * 64,
    PNG_MAGIC[:4],
    b"\xff\xd8\xff" + b"\x00" * 64,
    b"\xff\xd8"[:2],
])
def test_invalid_payloads_rejected(client, payload):
    sid = _start_and_code(client)
    r = _upload(client, sid, payload)
    assert r.status_code == 400


def test_png_magic_corrupt_body_rejected(client):
    sid = _start_and_code(client)
    valid = bytearray(PNG_FIXTURE.read_bytes())
    for i in range(16, len(valid)):
        valid[i] ^= 0xFF
    r = _upload(client, sid, bytes(valid))
    assert r.status_code == 400


def test_png_truncated_rejected(client):
    sid = _start_and_code(client)
    valid = PNG_FIXTURE.read_bytes()
    r = _upload(client, sid, valid[:len(valid) // 2])
    assert r.status_code == 400


def test_jpeg_magic_corrupt_body_rejected(client):
    sid = _start_and_code(client)
    valid = bytearray(JPG_FIXTURE.read_bytes())
    for i in range(8, len(valid)):
        valid[i] ^= 0xFF
    r = _upload(client, sid, bytes(valid))
    assert r.status_code == 400


def test_jpeg_truncated_rejected(client):
    sid = _start_and_code(client)
    valid = JPG_FIXTURE.read_bytes()
    r = _upload(client, sid, valid[:len(valid) // 2])
    assert r.status_code == 400


def test_inconsistent_mime_rejected(client):
    # real PNG bytes lying about being a JPEG: format must match declared MIME
    sid = _start_and_code(client)
    r = _ok_upload(client, sid, PNG_FIXTURE.read_bytes(), "rx.jpg", "image/jpeg")
    assert r.status_code == 400
    assert "not a valid image" in r.json()["detail"]


def test_wrong_mime_rejected(client):
    sid = _start_and_code(client)
    r = _ok_upload(client, sid, PNG_FIXTURE.read_bytes(), "rx.txt", "text/plain")
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_oversized_rejected_before_ocr(client):
    sid = _start_and_code(client)
    big = PNG_MAGIC + b"\x00" * (8 * 1024 * 1024)
    r = _upload(client, sid, big)
    assert r.status_code == 413