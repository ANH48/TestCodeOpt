import pytest

from optibot.config import load_settings


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    # Keep a developer's local .env out of the tests.
    monkeypatch.setattr("optibot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_api_key_alias_is_accepted():
    assert load_settings().gemini_api_key == "test-key"


@pytest.mark.parametrize("name,value", [
    ("CHUNK_MAX_TOKENS", "10"),
    ("CHUNK_OVERLAP_TOKENS", "300"),
    ("UPLOAD_WORKERS", "0"),
])
def test_invalid_settings_fail_fast(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        load_settings()
