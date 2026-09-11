import json
import os
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ocr_provider

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PNG = ROOT / "frontend" / "sample-prescription.png"
FIXTURE_JPG = ROOT / "frontend" / "sample-prescription.jpg"


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DATABASE_PATH"] = os.path.join(tmpdir, "test_fixture.db")
        with TestClient(app) as c:
            yield c
        os.environ.pop("DATABASE_PATH", None)


def test_sample_fixtures_are_real_decodable_images():
    assert FIXTURE_PNG.is_file(), f"missing {FIXTURE_PNG}"
    with open(FIXTURE_PNG, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "PNG magic bytes missing"
    width, height = struct.unpack(">II", head[16:24])
    assert (width, height) == (640, 480), f"unexpected dims {width}x{height}"


def test_sample_fixtures_pass_image_validation():
    from backend.routers.session import _looks_like_image

    assert _looks_like_image(FIXTURE_PNG.read_bytes()) is True
    assert _looks_like_image(FIXTURE_JPG.read_bytes()) is True


async def _fake_ocr(self, image_bytes, mime):
    return json.dumps({
        "medicine": "Metformin", "strength": "500 mg", "dose": "One tablet",
        "frequency": "Twice daily", "confidence": 0.9,
    })


def _start_and_code(client):
    r = client.post("/session/start", json={
        "patient": {"name": "Fixture Test", "age": 40, "gender": "female"},
        "language": "en", "visit_type": "new",
    })
    sid = r.json()["session_id"]
    client.post(f"/session/{sid}/consent", json={"consent_given": True})
    client.post(f"/session/{sid}/patient-code")
    return sid


def test_fixture_uploads_through_ocr_api(client):
    sid = _start_and_code(client)
    with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _fake_ocr):
        r = client.post(f"/session/{sid}/upload",
                        files={"file": ("sample-prescription.png", FIXTURE_PNG.read_bytes(), "image/png")})
    assert r.status_code == 200
    assert r.json()["medicine"] == "Metformin"
    assert r.json()["needs_review"] is False