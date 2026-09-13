import json

import pytest
from backend.services.llm_provider import (
    GeminiProvider,
    GroqProvider,
    CerebrasProvider,
    NvidiaNimProvider,
    OpenRouterProvider,
    LLMProvider,
    iter_llm_providers,
    get_llm_provider,
    LLM_CHAIN,
    provider_diagnostics,
)
from backend.services.ocr_provider import GeminiVisionProvider, GroqVisionProvider, VisionProvider
from backend.services.speech_provider import SarvamSpeechProvider, GroqWhisperProvider, SpeechProvider


def test_provider_abstractions():
    gemini_llm = GeminiProvider(api_key="test_key")
    assert isinstance(gemini_llm, LLMProvider)
    assert gemini_llm.provider_name == "gemini"
    assert gemini_llm.is_configured() is True

    groq_llm = GroqProvider(api_key="")
    assert isinstance(groq_llm, LLMProvider)
    assert groq_llm.provider_name == "groq"
    assert groq_llm.is_configured() is False

    gemini_vision = GeminiVisionProvider(api_key="test_key")
    assert isinstance(gemini_vision, VisionProvider)
    assert gemini_vision.provider_name == "gemini"

    groq_vision = GroqVisionProvider(api_key="your_groq_api_key_here")
    assert isinstance(groq_vision, VisionProvider)
    assert groq_vision.is_configured() is False

    sarvam_speech = SarvamSpeechProvider(api_key="test_key")
    assert isinstance(sarvam_speech, SpeechProvider)
    assert sarvam_speech.provider_name == "sarvam"

    whisper_speech = GroqWhisperProvider(api_key="test_key")
    assert isinstance(whisper_speech, SpeechProvider)
    assert whisper_speech.provider_name == "groq"


def test_new_providers_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    assert NvidiaNimProvider().is_configured() is False
    assert OpenRouterProvider().is_configured() is False
    assert GroqProvider().is_configured() is False
    assert CerebrasProvider().is_configured() is False


def test_new_providers_configured_with_keys(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk-test")
    assert NvidiaNimProvider().is_configured() is True
    assert OpenRouterProvider().is_configured() is True
    assert GroqProvider().is_configured() is True
    assert CerebrasProvider().is_configured() is True
    assert NvidiaNimProvider().provider_name == "nvidia_nim"
    assert OpenRouterProvider().provider_name == "openrouter"
    assert CerebrasProvider().provider_name == "cerebras"


def test_nvidia_nim_capped_timeout():
    p = NvidiaNimProvider()
    assert p._timeout == 7.0


def test_placeholders_rejected(monkeypatch):
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "your_key_here")
    monkeypatch.setenv("OPENROUTER_API_KEY", "CHANGE_ME")
    monkeypatch.setenv("CEREBRAS_API_KEY", "placeholder")
    assert NvidiaNimProvider().is_configured() is False
    assert OpenRouterProvider().is_configured() is False
    assert CerebrasProvider().is_configured() is False


@pytest.mark.parametrize("bad_key", [
    "***", "****", "  ***  ", "gsk-***", "sk-or-v1-********",
])
def test_masked_key_placeholder_rejected(monkeypatch, bad_key):
    monkeypatch.setenv("GROQ_API_KEY", bad_key)
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    assert GroqProvider().is_configured() is False


def test_empty_key_rejected(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    assert GroqProvider().is_configured() is False


def test_whitespace_key_rejected(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "   \t  ")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    assert GroqProvider().is_configured() is False


# Explicitly-empty args must not fall through to the environment, otherwise a
# valid key elsewhere in os.environ makes an "empty" provider report configured.
# These two are the regression tests for that constructor bug and are order-
# independent by construction (they pass whether or not real keys are present).
def test_explicit_empty_key_rejected_even_when_env_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-REALKEYINENV")
    assert GroqProvider(api_key="").is_configured() is False


def test_explicit_whitespace_key_rejected_even_when_env_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-REALKEYINENV")
    assert GroqProvider(api_key="   ").is_configured() is False


def test_explicit_model_beats_env(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "env-model")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    provider = GroqProvider(api_key="explicit-key", model_name="explicit-model")
    assert provider.api_key == "explicit-key"
    assert provider.model_name == "explicit-model"


def test_legitimate_groq_key_accepted(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-stretiv3q98pcgW1Ak2aNTGaBycDOnj9GsGNyVdjPuL0dlJeFmUx")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    provider = GroqProvider()
    assert provider.is_configured() is True
    assert provider.model_name == "llama-3.3-70b-versatile"


def test_provider_diagnostics_never_leaks_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-SUPERSECRET123")
    diag = provider_diagnostics()
    blob = json.dumps(diag)
    assert "SUPERSECRET" not in blob
    assert diag["groq"]["api_key"] == "set"
    assert diag["nvidia_nim"]["api_key"] == "missing"


def test_chain_order_is_groq_cerebras_nim():
    assert LLM_CHAIN == [GroqProvider, CerebrasProvider, NvidiaNimProvider]


def test_iter_llm_providers_priority(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = iter_llm_providers()
    assert [p.provider_name for p in providers] == ["groq"]


def test_iter_llm_providers_skips_unconfigured(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = iter_llm_providers()
    assert [p.provider_name for p in providers] == ["nvidia_nim"]


def test_iter_llm_providers_all_three(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk-test")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = iter_llm_providers()
    assert [p.provider_name for p in providers] == ["groq", "cerebras", "nvidia_nim"]


def test_iter_llm_providers_raises_when_none(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        iter_llm_providers()


def test_get_llm_provider_returns_first(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test")
    assert get_llm_provider().provider_name == "groq"


@pytest.mark.asyncio
async def test_nvidia_nim_failover_on_timeout():
    from unittest.mock import AsyncMock
    import httpx
    from backend.services.llm_provider import generate_adaptive_turn

    nim = NvidiaNimProvider(api_key="nvapi-test")
    # Simulate slow/timeout NVIDIA NIM call (raises ReadTimeout under capped 7s timeout)
    nim.generate = AsyncMock(side_effect=httpx.ReadTimeout("Request timed out after 7.0s"))

    cerebras = CerebrasProvider(api_key="csk-test")
    cerebras.generate = AsyncMock(return_value=json.dumps({
        "case_update": {
            "presentation": "digestive",
            "concepts": {"site": "stomach"},
            "denied_concepts": [],
            "mentioned_documents": [],
        },
        "next_question": {
            "text": "How long has it been hurting?",
            "target_concept": "duration",
            "reason": "Assess timeline",
            "priority": "high",
        },
        "status": "continue",
        "confidence": 0.9,
    }))

    context = {
        "language": "en",
        "presentation_domain": "Digestive",
        "interview_step": "hpi",
        "collected_concepts": {},
        "denied_concepts": [],
        "last_patient_answer": "My stomach hurts",
        "turns_count": 1,
        "questions_asked": [],
    }

    result = await generate_adaptive_turn(context, providers=[nim, cerebras])
    assert result is not None
    assert result["provider"] == "cerebras"
    assert nim.generate.called
    assert cerebras.generate.called
