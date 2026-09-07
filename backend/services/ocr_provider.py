import os
from abc import ABC, abstractmethod
from typing import Optional
from backend.models.schema import MedicineExtraction

class VisionProvider(ABC):
    """Abstract base interface for OCR and Vision extraction providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[MedicineExtraction]:
        pass

class GeminiVisionProvider(VisionProvider):
    """Primary OCR / Vision Provider using Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[MedicineExtraction]:
        if not self.is_configured():
            raise RuntimeError("Gemini API key is not configured")
        # Placeholder for full vision extraction logic in Day 4
        return None

class GroqVisionProvider(VisionProvider):
    """Backup OCR / Vision Provider using Groq."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama-3.2-11b-vision-preview"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "groq"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def extract_prescription(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[MedicineExtraction]:
        if not self.is_configured():
            raise RuntimeError("Groq API key is not configured")
        # Placeholder for backup vision extraction logic in Day 4
        return None
