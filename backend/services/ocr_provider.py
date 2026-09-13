"""Vision/OCR document extraction with provider abstraction.

Gemini Vision (`gemini-2.5-flash`) is the primary provider; Groq Vision
(`llama-3.2-11b-vision-preview`) is the fallback. Provider ordering lives HERE,
never in a router. All provider output is validated with Pydantic
(`MedicineExtraction`, extra fields rejected) before it is trusted.

Confidence gating is an application decision (`OCR_CONFIDENCE_THRESHOLD`),
applied by the caller — never decided by the provider/LLM.

Deployment note: real patient data must only be sent to a paid/approved API
tier. Demo/integration runs use synthetic fixtures and mocked providers, never
real patient data against free-tier endpoints.
"""
import base64
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

from backend.models.schema import MedicineExtraction

# Fixed application threshold. Provider output below this is never trusted.
OCR_CONFIDENCE_THRESHOLD = 0.5

_EXTRACTION_PROMPT = (
    "You are extracting structured information from a medical prescription "
    "image. Return ONLY valid JSON with EXACTLY these keys: "
    '"medicine", "strength", "dose", "frequency", "confidence" (0.0 to 1.0). '
    "If the medicine name cannot be read clearly, set \"medicine\" to null — "
    "never guess. If a field is not present in the image, set it to null. "
    "Do not add any other keys and do not include prose or code fences."
)


class OCRUnavailableError(Exception):
    """All configured vision providers failed or none were configured."""


class VisionProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: pass

    @abstractmethod
    def is_configured(self) -> bool: pass

    @abstractmethod
    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[str]: pass


class GeminiVisionProvider(VisionProvider):
    """Primary OCR / Vision provider using Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name or os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def _get_client(self):
        if not self._client and self.is_configured():
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Gemini API key is not configured")
        from google.genai import types as genai_types
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model_name,
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _EXTRACTION_PROMPT,
            ],
        )
        return response.text if response else None


class GroqVisionProvider(VisionProvider):
    """Backup OCR / Vision provider using Groq."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model_name = model_name or os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "groq"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def _get_client(self):
        if not self._client and self.is_configured():
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self.api_key)
        return self._client

    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Groq API key is not configured")
        client = self._get_client()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        chat_completion = await client.chat.completions.create(
            model=self.model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            }],
        )
        return chat_completion.choices[0].message.content


def _strip_fences(raw: str) -> str:
    # Remove reasoning / thought blocks (e.g. <think>...</think>)
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    # Extract JSON object boundary if surrounded by prose
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return match.group(0)
    return text


def parse_extraction(raw: str) -> MedicineExtraction:
    """Strict-parse provider text into MedicineExtraction.

    Rejects unexpected fields (Pydantic extra='forbid') and unreadable text.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty OCR response")
    clean = _strip_fences(raw)
    data = json.loads(clean)
    if not isinstance(data, dict):
        raise ValueError("OCR response was not a JSON object")
    if "confidence" in data and isinstance(data["confidence"], str):
        try:
            data["confidence"] = float(data["confidence"])
        except ValueError:
            data["confidence"] = 0.95 if "high" in data["confidence"].lower() else 0.5
    return MedicineExtraction.model_validate(data)


async def run_document_ocr(image_bytes: bytes, mime_type: str) -> Tuple[MedicineExtraction, str, Dict[str, Any]]:
    """Run OCR with Gemini primary, Groq fallback.

    Returns (validated extraction, provider_name_used, raw_provider_json).
    Raises OCRUnavailableError when every provider fails or none is configured.
    """
    failures: list[str] = []
    for cls in (GeminiVisionProvider, GroqVisionProvider):
        provider = cls()
        if not provider.is_configured():
            failures.append(f"{provider.provider_name}: not configured")
            continue
        try:
            raw = await provider.extract_prescription(image_bytes, mime_type)
            extraction = parse_extraction(raw)
            raw_json = json.loads(_strip_fences(raw))
            return extraction, provider.provider_name, raw_json if isinstance(raw_json, dict) else {"raw": raw}
        except Exception as exc:  # noqa: BLE001 - provider failure must never crash the request
            failures.append(f"{provider.provider_name}: {type(exc).__name__}: {str(exc)[:120]}")
    raise OCRUnavailableError("; ".join(failures) or "No vision provider configured")