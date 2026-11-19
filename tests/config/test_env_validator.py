import pytest

from app.config.env_validator import EnvironmentValidator


def _clear_provider_environment(monkeypatch):
    for name in (
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "LLM_PROVIDER",
        "EMBEDDING_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.unit
def test_gemini_can_be_selected_for_chat_and_embeddings_without_openai_key(
    monkeypatch,
):
    _clear_provider_environment(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    validator = EnvironmentValidator(strict_mode=False)

    validator.validate_all()

    assert validator.validation_warnings == []


@pytest.mark.unit
def test_openai_key_is_required_when_an_openai_provider_is_selected(monkeypatch):
    _clear_provider_environment(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    validator = EnvironmentValidator(strict_mode=False)

    validator.validate_all()

    assert any("OPENAI_API_KEY is required" in warning for warning in validator.validation_warnings)


@pytest.mark.unit
def test_gemini_key_is_required_when_a_gemini_provider_is_selected(monkeypatch):
    _clear_provider_environment(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-" + "x" * 24)
    validator = EnvironmentValidator(strict_mode=False)

    validator.validate_all()

    assert any("GEMINI_API_KEY is required" in warning for warning in validator.validation_warnings)


@pytest.mark.unit
def test_unused_invalid_openai_key_does_not_block_gemini_only_configuration(
    monkeypatch,
):
    _clear_provider_environment(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "expired-or-placeholder")
    validator = EnvironmentValidator(strict_mode=False)

    validator.validate_all()

    assert validator.validation_warnings == []


@pytest.mark.unit
def test_invalid_openai_key_is_rejected_when_openai_is_selected(monkeypatch):
    _clear_provider_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "invalid")
    validator = EnvironmentValidator(strict_mode=False)

    validator.validate_all()

    assert any("must start with 'sk-'" in warning for warning in validator.validation_warnings)
