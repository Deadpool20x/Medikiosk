"""P0 audit screenshot server: the real FastAPI app with deterministic provider
mocks, served over HTTP so the real Next.js frontend can be driven by a browser.

This mirrors the backend test mocks exactly (same patch targets, same payloads)
so the live browser flow is byte-for-byte deterministic with the pytest suite.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

import uvicorn

from backend.main import app
from backend.routers import session as session_router
from backend.services import ocr_provider

DB_PATH = os.environ.get("P0_DB")
assert DB_PATH, "P0_DB must point to the SQLite file to use"

os.environ["DATABASE_PATH"] = DB_PATH


class _FakeProvider:
    provider_name = "gemini"


def mock_extract(provider, field, ans):
    if field == "chief_complaint":
        return {"complaint": ans.strip(), "confidence": 0.9}
    if field == "associated_symptoms":
        return {"associated_symptoms": [ans.strip()], "confidence": 0.9}
    return {field: ans.strip(), "confidence": 0.9}


_VALID_OCR = json.dumps({
    "medicine": "Metformin", "strength": "500 mg", "dose": "one tablet",
    "frequency": "twice daily", "confidence": 0.92,
})


async def _mock_ocr(self, image_bytes, mime):
    return _VALID_OCR


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
         patch.object(session_router, "extract_field", side_effect=mock_extract), \
         patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
         patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", _mock_ocr):
        uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")