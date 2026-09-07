import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class LLMProvider(ABC):
    """Abstract base interface for LLM text completion/extraction providers."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier for the provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Verify if required API keys and configuration are present."""
        pass

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """Generate text completion."""
        pass

class GeminiProvider(LLMProvider):
    """Primary LLM Provider using Google GenAI SDK."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
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

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Gemini API key is not configured")
        client = self._get_client()
        config: Dict[str, Any] = {}
        if system_prompt:
            config["system_instruction"] = system_prompt
        
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config if config else None
        )
        return response.text if response else None

class GroqProvider(LLMProvider):
    """Backup LLM Provider using Groq SDK."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model_name = model_name
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

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("Groq API key is not configured")
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        chat_completion = await client.chat.completions.create(
            messages=messages,
            model=self.model_name
        )
        return chat_completion.choices[0].message.content
