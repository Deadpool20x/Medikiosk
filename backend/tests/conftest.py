import pytest

PROVIDER_API_KEYS = [
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
]


@pytest.fixture(autouse=True)
def _no_provider_keys(monkeypatch):
    """Keep provider API keys out of os.environ for hermetic tests.

    The real .env is loaded whenever backend.main is imported (load_dotenv at
    import time), so without clearing these, tests would run against live keys
    from the developer's machine. Tests that need a key call
    monkeypatch.setenv explicitly.
    """
    for key in PROVIDER_API_KEYS:
        monkeypatch.delenv(key, raising=False)