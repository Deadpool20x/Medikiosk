import os
from abc import ABC, abstractmethod
from typing import Optional

class SpeechProvider(ABC):
    """Abstract base interface for speech-to-text providers (Stretch Day 5)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language_code: str = "hi-IN") -> Optional[str]:
        pass

class SarvamSpeechProvider(SpeechProvider):
    """Primary STT provider using Sarvam AI Saaras v3."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "sarvam"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def transcribe(self, audio_bytes: bytes, language_code: str = "hi-IN") -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Sarvam API key is not configured")
        return None

class GroqWhisperProvider(SpeechProvider):
    """Backup STT provider using Groq Whisper Large v3."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "whisper-large-v3"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "groq"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def transcribe(self, audio_bytes: bytes, language_code: str = "hi-IN") -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Groq API key is not configured")
        return None
