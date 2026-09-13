import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Literal

import httpx

from pydantic import BaseModel, Field, ConfigDict

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


def _clean_json_text(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0).strip()
    return text


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    cleaned = _clean_json_text(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Strip trailing commas before closing braces/brackets
        sanitized = re.sub(r",\s*([\}\]])", r"\1", cleaned)
        return json.loads(sanitized)


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
        content = msg.get("content")
        if not content and msg.get("reasoning"):
            content = msg.get("reasoning")
        return content

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
            data = _parse_llm_json(response)
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


class CaseExtraction(BaseModel):
    """Strict structured case extraction contract for the adaptive engine.

    The deterministic engine is authoritative for question selection; this
    model only conveys what the patient's answer said. Domain and concept keys
    are validated against the engine's whitelists before anything is applied.
    """
    model_config = ConfigDict(extra="forbid")

    domain: Optional[str] = None
    concepts: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    mentioned_documents: List[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    presentation: Optional[str] = None
    concepts: Dict[str, Any] = Field(default_factory=dict)
    denied_concepts: List[str] = Field(default_factory=list)
    mentioned_documents: List[str] = Field(default_factory=list)


class NextQuestionProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    target_concept: str
    reason: str = ""
    priority: Literal["high", "normal", "optional"] = "normal"


class AdaptiveTurnProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    case_update: CaseUpdate = Field(default_factory=CaseUpdate)
    next_question: Optional[NextQuestionProposal] = None
    status: Literal["continue", "sufficient", "clarify"] = "continue"
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


async def generate_adaptive_turn(
    session_context: Dict[str, Any],
    providers: Optional[List[LLMProvider]] = None,
) -> Dict[str, Any]:
    """Generate conversational intake interpretation, structured case updates,
    and the next patient-facing follow-up question via LLM.

    The LLM acts as the conversational interviewer while strict deterministic
    guards validate the output before it is accepted.
    """
    from backend.rules.adaptive_interview import ALL_DOMAINS, ALL_ALLOWED_CONCEPTS

    allowed_domains = sorted(ALL_DOMAINS)
    allowed_concepts = sorted(ALL_ALLOWED_CONCEPTS)
    language = session_context.get("language", "en")

    lang_instructions = {
        "hi": (
            "The patient's language is Hindi (hi). Generate next_question.text in simple, "
            "polite, conversational Hindi (Devanagari script), as a COMPLETE question starting "
            "with a question word such as क्या, कितने, कब, कहाँ, कैसे, कैसा. Never use an "
            "elliptical fragment and never drop the subject. Keep all concept keys and JSON in English."
        ),
        "gu": (
            "The patient's language is Gujarati (gu). Generate next_question.text in simple, "
            "polite, conversational Gujarati (Gujarati script), as a COMPLETE question starting "
            "with a question word such as શું, કેટલા, ક્યારે, ક્યાં, કયા, કેવી, કેવું. Never use "
            "an elliptical fragment (never begin with નથી) and never drop the subject. "
            "Keep all concept keys and JSON in English."
        ),
        "en": (
            "The patient's language is English (en). Generate next_question.text in clear, "
            "respectful, non-technical English."
        ),
    }.get(language, "Generate next_question.text in clear, respectful, non-technical English.")

    denial_hint = session_context.get("denial_hint", "")
    normalized_hint = ""
    norm_map = session_context.get("language_normalized_symptoms") or {}
    if norm_map:
        normalized_hint = (
            "The patient answered in a regional language. The following canonical meanings were "
            "recognized (use these, never invent different meanings): "
            + json.dumps(norm_map)
        )

    system_prompt = (
        "You are an empathetic, clinical OPD intake conversational interviewer for MediKiosk. "
        "Your task is to understand the patient's natural language answer, update structured concepts, "
        "and propose the next most clinically useful follow-up question.\n\n"
        "STRICT CONVERSATIONAL AND CLINICAL INVARIANTS:\n"
        "1. NEVER DIAGNOSE. Never suggest a condition, illness, dosha imbalance, or disease name.\n"
        "2. NEVER PRESCRIBE OR TREAT. Never recommend medicines, herbs, dosages, treatments, or Panchakarma.\n"
        "3. NEVER ASK FOR A FACT ALREADY SUFFICIENTLY ESTABLISHED. If a concept has a value in collected_concepts, "
        "do NOT ask for it again unless asking for necessary clarification.\n"
        "4. TREAT EXPLICIT NEGATIVES AS ESTABLISHED ABSENT FINDINGS. If the patient denies a symptom (e.g. 'no fever', 'no vomiting'), "
        "record it in denied_concepts and NEVER ask about it again unless clarifying.\n"
        "5. DO NOT INFER A DIFFERENT BODY SYSTEM WITHOUT EVIDENCE. Ground your interpretation strictly in the patient's words. "
        "Never convert stomach symptoms into jaw pain, or cough into knee pain.\n"
        "6. DO NOT CONVERT UNCERTAINTY INTO CERTAINTY. If regional language or statement is ambiguous, ask clarification.\n"
        "7. ONE CLEAR PATIENT-FRIENDLY QUESTION. Propose exactly ONE question using patient-friendly language.\n"
        "8. DO NOT EXPOSE INTERNAL CONCEPT NAMES. Never say words like 'laterality', 'functional limitation', 'character', or 'site' directly.\n"
        "9. CATEGORY COMPATIBILITY. Do not ask pain descriptors (sharp/dull/numbness) on metabolic weakness or fatigue.\n"
        "10. AYURVEDIC TERMS (e.g., Agni, Ama, Vata) must remain provisional/literature-informed and must never imply disease diagnosis.\n"
        f"11. LANGUAGE: {lang_instructions}\n"
        "12. STRUCTURED JSON OUTPUT ONLY. Respond with valid JSON matching:\n"
        "{\n"
        '  "case_update": {\n'
        f'    "presentation": "one of {json.dumps(allowed_domains)}",\n'
        f'    "concepts": {{ "concept_key": "patient statement" }},\n'
        '    "denied_concepts": ["denied symptom, e.g. fever, vomiting"],\n'
        '    "mentioned_documents": ["document mentioned by patient or empty list"]\n'
        "  },\n"
        '  "next_question": {\n'
        '    "text": "The patient-facing question in the requested language",\n'
        '    "target_concept": "the specific concept being explored",\n'
        '    "reason": "short clinical reason why this question is helpful",\n'
        '    "priority": "high|normal|optional"\n'
        "  },\n"
        '  "status": "continue|sufficient|clarify",\n'
        '  "confidence": 0.85\n'
        "}\n"
        f"Allowed concept keys: {json.dumps(allowed_concepts)}.\n"
        f"13. {denial_hint + ' ' if denial_hint else ''}"
        f"{normalized_hint + ' ' if normalized_hint else ''}"
    )

    user_prompt = (
        f"Current Session Context:\n{json.dumps(session_context, indent=2)}\n\n"
        "Analyze the patient's current answer, update collected concepts, and propose the next question."
    )

    if providers is None:
        providers = iter_llm_providers()

    last_error: Optional[Exception] = None
    for provider in providers:
        try:
            response = await provider.generate(user_prompt, system_prompt=system_prompt)
            if not response:
                raise RuntimeError("Empty response from LLM provider")
            data = _parse_llm_json(response)
            parsed = AdaptiveTurnProposal.model_validate(data)

            # Sanitize concepts
            sanitized_concepts = {}
            for k, v in parsed.case_update.concepts.items():
                if k in allowed_concepts and v is not None and str(v).strip():
                    sanitized_concepts[k] = str(v).strip()
            parsed.case_update.concepts = sanitized_concepts

            return {
                "case_update": parsed.case_update.model_dump(),
                "next_question": parsed.next_question.model_dump() if parsed.next_question else None,
                "status": parsed.status,
                "confidence": parsed.confidence,
                "provider": provider.provider_name,
            }
        except Exception as e:
            err_msg = str(e) if str(e).strip() else repr(e)
            logger.warning("Provider %s failed during adaptive turn: %s", provider.provider_name, err_msg)
            last_error = e
            continue

    raise RuntimeError(f"All LLM providers failed: {last_error}")


async def correct_adaptive_turn(
    session_context: Dict[str, Any],
    validation_reasons: List[str],
    recovery_hint: Optional[str] = None,
    providers: Optional[List[LLMProvider]] = None,
) -> Optional[Dict[str, Any]]:
    """One-shot bounded self-correction: ask the LLM to fix its rejected proposal.

    The deterministic validator's reasons and hint are fed back once. The
    output goes through the exact same sanitization as `generate_adaptive_turn`.
    Returns None if every provider fails, so the caller falls back cleanly.
    Never loops: the router calls this at most once per turn.
    """
    from backend.rules.adaptive_interview import ALL_DOMAINS, ALL_ALLOWED_CONCEPTS

    allowed_domains = sorted(ALL_DOMAINS)
    allowed_concepts = sorted(ALL_ALLOWED_CONCEPTS)
    language = session_context.get("language", "en")

    lang_instructions = {
        "hi": ("Respond in simple, polite conversational Hindi (Devanagari script) as a COMPLETE question "
               "starting with a question word such as क्या, कितने, कब, कहाँ. Never use an elliptical fragment. "
               "Keep concept keys and JSON in English."),
        "gu": ("Respond in simple, polite conversational Gujarati (Gujarati script) as a COMPLETE question "
               "starting with a question word such as શું, કેટલા, ક્યારે, ક્યાં. Never use an elliptical "
               "fragment (never begin with નથી). Keep concept keys and JSON in English."),
        "en": ("Respond in clear, respectful, non-technical English."),
    }.get(language, "Respond in clear, respectful, non-technical English.")

    feedback = (
        "Your previous proposal was REJECTED by the clinical policy validator.\n"
        f"Reasons:\n- " + "\n- ".join(validation_reasons) + "\n"
        + (f"Hint: {recovery_hint}\n" if recovery_hint else "")
        + "Fix ALL reasons. In particular: pick a DIFFERENT concept that is unanswered, unasked, "
        "not denied by the patient, and appropriate for the presentation domain. "
        "Never repeat a previously asked question."
    )

    system_prompt = (
        "You are the MediKiosk intake interviewer being asked to correct a rejected follow-up proposal. "
        "Respond with EXACTLY the same JSON schema as before.\n"
        f"Allowed domains: {json.dumps(allowed_domains)}. "
        f"Allowed concept keys: {json.dumps(allowed_concepts)}.\n"
        f"Language: {lang_instructions}\n"
        "STRICT:\n"
        "1. NEVER diagnose, prescribe, or treat.\n"
        "2. target_concept must be one specific allowed concept.\n"
        "3. Never use internal concept names in the question text.\n"
        "4. If the concept you chose before was rejected as already answered/asked, choose instead "
        "the single most clinically useful UNASKED concept relevant to this presentation.\n"
    )

    user_prompt = (
        f"Current Session Context:\n{json.dumps(session_context, indent=2)}\n\n"
        f"Validator Feedback:\n{feedback}\n\n"
        "Return ONLY the corrected JSON proposal."
    )

    if providers is None:
        providers = iter_llm_providers()

    last_error: Optional[Exception] = None
    for provider in providers:
        try:
            response = await provider.generate(user_prompt, system_prompt=system_prompt)
            if not response:
                raise RuntimeError("Empty response from LLM provider")
            data = _parse_llm_json(response)
            parsed = AdaptiveTurnProposal.model_validate(data)

            sanitized_concepts = {}
            for k, v in parsed.case_update.concepts.items():
                if k in allowed_concepts and v is not None and str(v).strip():
                    sanitized_concepts[k] = str(v).strip()
            parsed.case_update.concepts = sanitized_concepts

            return {
                "case_update": parsed.case_update.model_dump(),
                "next_question": parsed.next_question.model_dump() if parsed.next_question else None,
                "status": parsed.status,
                "confidence": parsed.confidence,
                "provider": provider.provider_name,
                "corrected": True,
            }
        except Exception as e:
            err_msg = str(e) if str(e).strip() else repr(e)
            logger.warning("Provider %s failed during correction: %s", provider.provider_name, err_msg)
            last_error = e
            continue

    if last_error:
        raise RuntimeError(f"All LLM providers failed during correction: {last_error}")
    return None


async def extract_case(
    patient_answer: str,
    current_concept: Optional[str] = None,
    domain_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Structured case extraction: one LLM call yields multiple concepts,
    a suggested presentation domain, and document mentions.

    Returns dict with keys: domain, concepts, confidence, mentioned_documents,
    provider. Validation is strict (extra fields rejected, only whitelisted
    concept/domain keys accepted). Raises only if every configured provider
    fails or returns a malformed payload. The caller (router) treats a raising
    call as an extraction failure and falls back to deterministic routing.
    """
    from backend.rules.adaptive_interview import ALL_DOMAINS, ALL_ALLOWED_CONCEPTS

    allowed_domains = set(ALL_DOMAINS)
    allowed_concepts = set(ALL_ALLOWED_CONCEPTS)

    system_prompt = (
        "You extract structured medical intake facts from ONE patient answer about a kiosk "
        "health interview. Respond with ONLY valid JSON and EXACTLY these keys: "
        '"domain", "concepts", "confidence", "mentioned_documents". '
        f'"domain" must be one of {json.dumps(sorted(allowed_domains))} or null when the answer '
        "does not clearly indicate one. "
        f'"concepts" is an object whose keys may ONLY be chosen from '
        f"{json.dumps(sorted(allowed_concepts))}; set a key to null when the patient did not "
        "mention it — never guess or invent values not stated. Track the concept currently being "
        "asked and bias each concept's value toward what the patient literally said. "
        '"confidence" is a number 0-1. "mentioned_documents" is an array of document types '
        '(e.g. "blood report", "prescription", "x-ray report") the patient says they have, or []. '
        "Never include any diagnosis, treatment, or clinical judgment."
    )

    providers = iter_llm_providers()
    last_error: Optional[Exception] = None
    for provider in providers:
        try:
            response = await provider.generate(patient_answer, system_prompt=system_prompt)
            if not response:
                raise RuntimeError("Empty response from LLM provider")
            data = _parse_llm_json(response)
            parsed = CaseExtraction.model_validate(data)
            if parsed.domain and parsed.domain not in allowed_domains:
                raise ValueError(f"LLM returned unknown domain: {parsed.domain}")
            bad_concepts = set(parsed.concepts) - allowed_concepts
            if bad_concepts:
                raise ValueError(f"LLM returned unknown concepts: {sorted(bad_concepts)}")
            for key, value in parsed.concepts.items():
                if value is None:
                    parsed.concepts[key] = ""
            return {
                "domain": parsed.domain,
                "concepts": parsed.concepts,
                "confidence": parsed.confidence,
                "mentioned_documents": parsed.mentioned_documents or [],
                "provider": provider.provider_name,
            }
        except Exception as e:
            err_msg = str(e) if str(e).strip() else repr(e)
            logger.warning("Provider %s failed during extract_case: %s", provider.provider_name, err_msg)
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
    data = _parse_llm_json(response)
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
