import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: pass

    @abstractmethod
    def is_configured(self) -> bool: pass

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]: pass


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered.startswith("your_"):
        return True
    # Common placeholder substrings the user might paste before rotating keys.
    for marker in ("changeme", "change_me", "replace_me", "todo", "xxx",
                    "***", "placeholder", "<your", "{your"):
        if marker in lowered:
            return True
    return False


class OpenAICompatibleProvider(LLMProvider):
    """Base for any OpenAI Chat-Completions-compatible endpoint."""
    default_model: str = ""
    env_key: str = ""
    env_model_key: str = ""
    base_url: str = ""
    name: str = ""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: float = 30.0):
        # Only fall back to the environment when the caller did not pass a value.
        # `or` would let an explicitly empty/whitespace key read the env var and
        # wrongly report the provider as configured.
        resolved_key = api_key if api_key is not None else os.getenv(self.env_key, "")
        self.api_key = resolved_key.strip()
        resolved_model = model_name if model_name is not None else os.getenv(self.env_model_key, self.default_model)
        self.model_name = resolved_model.strip()
        if base_url:
            self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return self.name

    def is_configured(self) -> bool:
        return bool(self.api_key) and not _is_placeholder(self.api_key) and bool(self.model_name)

    async def _post_chat(self, messages: List[Dict[str, str]], extra_body: Optional[Dict[str, Any]] = None,
                         extra_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        url = f"{self.base_url}/chat/completions"
        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        }
        if extra_body:
            body.update(extra_body)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"{self.provider_name} HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        msg = choices[0].get("message") or {}
        return msg.get("content")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError(f"{self.provider_name} API key is not configured")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self._post_chat(messages, extra_body=kwargs.get("extra_body"))


class GroqProvider(OpenAICompatibleProvider):
    default_model = "openai/gpt-oss-20b"
    env_key = "GROQ_API_KEY"
    env_model_key = "GROQ_MODEL"
    base_url = "https://api.groq.com/openai/v1"
    name = "groq"


class NvidiaNimProvider(OpenAICompatibleProvider):
    default_model = "meta/llama-3.2-11b-vision-instruct"
    env_key = "NVIDIA_NIM_API_KEY"
    env_model_key = "NVIDIA_NIM_MODEL"
    base_url = "https://integrate.api.nvidia.com/v1"
    name = "nvidia_nim"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("nvidia_nim API key is not configured")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return await self._post_chat(
            messages,
            extra_body=kwargs.get("extra_body"),
            extra_headers={"Accept": "application/json"},
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    default_model = "meta-llama/llama-3.3-70b-instruct:free"
    env_key = "OPENROUTER_API_KEY"
    env_model_key = "OPENROUTER_MODEL"
    base_url = "https://openrouter.ai/api/v1"
    name = "openrouter"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        if not self.is_configured():
            raise RuntimeError("openrouter API key is not configured")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        # ZDR: route only to providers with zero-data-retention policy.
        # Also send a referer so OpenRouter treats the request as first-party.
        return await self._post_chat(
            messages,
            extra_body={"zdr": True, **(kwargs.get("extra_body") or {})},
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://medikiosk.local"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "MediKiosk"),
            },
        )


# Back-compat: keep GeminiProvider available for OCR/Vision imports elsewhere,
# but it is no longer wired into the LLM chat chain (PHI / training concerns).
class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        self.model_name = model_name
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(self.api_key) and not _is_placeholder(self.api_key)

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


# LLM chat chain order. Each provider is tried in sequence; on exception the
# next one is attempted. The chain is built from whatever is configured.
LLM_CHAIN: List[type] = [GroqProvider, NvidiaNimProvider, OpenRouterProvider]


def _configured_providers() -> List[LLMProvider]:
    configured: List[LLMProvider] = []
    for cls in LLM_CHAIN:
        provider = cls()
        if provider.is_configured():
            configured.append(provider)
    return configured


def provider_diagnostics() -> Dict[str, Any]:
    """Describe provider config state without revealing secrets.

    Only presence/placeholder status per env key is reported — never the key
    value. Used to give operators an actionable message when nothing is usable.
    """
    diagnostics: Dict[str, Any] = {}
    for cls in LLM_CHAIN:
        provider = cls()
        raw = provider.api_key
        status = "missing"
        if raw:
            status = "placeholder" if _is_placeholder(raw) else "set"
        diagnostics[provider.provider_name] = {
            "model": provider.model_name,
            "api_key": status,
        }
    return diagnostics


def get_llm_provider() -> LLMProvider:
    """Return the first configured provider. Kept for callers that want a single
    primary. Use `iter_llm_providers()` for fallback chains."""
    configured = _configured_providers()
    if not configured:
        logger.error("No LLM provider configured: %s", provider_diagnostics())
        raise RuntimeError("No LLM provider configured")
    return configured[0]


def iter_llm_providers() -> List[LLMProvider]:
    """Return all configured providers in priority order."""
    configured = _configured_providers()
    if not configured:
        logger.error("No LLM provider configured: %s", provider_diagnostics())
        raise RuntimeError("No LLM provider configured")
    return configured


async def extract_with_fallback(field: str, patient_answer: str) -> Dict[str, Any]:
    """Try each configured provider in order. Returns the first successful
    extraction plus metadata. Raises only if every provider failed."""
    from backend.rules.interview_rules import FIELD_SCHEMAS
    allowed_keys = list(FIELD_SCHEMAS.get(field, {}).keys())
    if not allowed_keys:
        raise ValueError(f"No schema defined for field: {field}")
    schema = {k: "string" for k in allowed_keys}
    system_prompt = (
        f"You are extracting structured medical intake data. Return ONLY valid JSON "
        f"matching this schema: {json.dumps(schema)}. Do not add fields not in this "
        f"schema. If a field is not mentioned in the patient's answer, return null for "
        f"it — do not guess or infer a value the patient did not state. Do not include "
        f"any diagnosis, treatment suggestion, or clinical judgment in your response."
    )

    providers = iter_llm_providers()
    last_error: Optional[Exception] = None
    for provider in providers:
        try:
            response = await provider.generate(patient_answer, system_prompt=system_prompt)
            if not response:
                raise RuntimeError("Empty response from LLM provider")
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            data = json.loads(cleaned)
            if not isinstance(data, dict) or set(data.keys()) != set(allowed_keys):
                raise ValueError(
                    f"LLM returned fields outside the allowed schema for {field}"
                )
            if "confidence" not in data:
                data["confidence"] = 0.8
            return {
                "data": data,
                "provider": provider.provider_name,
                "confidence": data.get("confidence", 0.8),
            }
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"All LLM providers failed: {last_error}")


async def extract_field(provider: LLMProvider, field: str, patient_answer: str) -> Dict[str, Any]:
    """Legacy single-provider extract. Kept for tests and external callers."""
    from backend.rules.interview_rules import FIELD_SCHEMAS
    allowed_keys = list(FIELD_SCHEMAS.get(field, {}).keys())
    if not allowed_keys:
        raise ValueError(f"No schema defined for field: {field}")
    schema = {k: "string" for k in allowed_keys}
    system_prompt = (
        f"You are extracting structured medical intake data. Return ONLY valid JSON "
        f"matching this schema: {json.dumps(schema)}. Do not add fields not in this "
        f"schema. If a field is not mentioned in the patient's answer, return null for "
        f"it — do not guess or infer a value the patient did not state. Do not include "
        f"any diagnosis, treatment suggestion, or clinical judgment in your response."
    )
    response = await provider.generate(patient_answer, system_prompt=system_prompt)
    if not response:
        raise RuntimeError("Empty response from LLM provider")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
    data = json.loads(cleaned)
    if not isinstance(data, dict) or set(data.keys()) != set(allowed_keys):
        raise ValueError(f"LLM returned fields outside the allowed schema for {field}")
    if "confidence" not in data:
        data["confidence"] = 0.8
    return data


async def extract_field_with_chain(field: str, patient_answer: str,
                                   providers: Optional[List[LLMProvider]] = None) -> Dict[str, Any]:
    """Iterate the configured LLM chain until one succeeds.

    Tests that patch `extract_field` directly will not be reached; tests that want
    to drive the chain should patch `extract_field_with_chain` instead, or pass
    their own `providers` list.
    """
    from backend.rules.interview_rules import FIELD_SCHEMAS
    allowed_keys = list(FIELD_SCHEMAS.get(field, {}).keys())
    if not allowed_keys:
        raise ValueError(f"No schema defined for field: {field}")
    schema = {k: "string" for k in allowed_keys}
    system_prompt = (
        f"You are extracting structured medical intake data. Return ONLY valid JSON "
        f"matching this schema: {json.dumps(schema)}. Do not add fields not in this "
        f"schema. If a field is not mentioned in the patient's answer, return null for "
        f"it — do not guess or infer a value the patient did not state. Do not include "
        f"any diagnosis, treatment suggestion, or clinical judgment in your response."
    )

    if providers is None:
        providers = iter_llm_providers()
    last_error: Optional[Exception] = None
    for idx, provider in enumerate(providers):
        try:
            data = await extract_field(provider, field, patient_answer)
            return {
                "data": data,
                "provider": provider.provider_name,
                "confidence": (
                    min(data.get("confidence", 0.8), 0.7) if idx > 0 else data.get("confidence", 0.8)
                ),
            }
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"All LLM providers failed: {last_error}")
