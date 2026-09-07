import pytest
from backend.services.llm_provider import GeminiProvider, GroqProvider, LLMProvider
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
