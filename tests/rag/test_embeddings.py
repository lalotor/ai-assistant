import pytest

from app.rag.embeddings import (
    DEFAULT_GEMINI_EMBEDDING_MODEL,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    get_embedding_config,
    get_embeddings,
)


@pytest.mark.unit
class TestEmbeddingProvider:
    def test_openai_remains_the_default_provider(self, mocker, monkeypatch):
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        openai_embeddings = mocker.patch("app.rag.embeddings.OpenAIEmbeddings")

        result = get_embeddings()

        openai_embeddings.assert_called_once_with(model=DEFAULT_OPENAI_EMBEDDING_MODEL)
        assert result is openai_embeddings.return_value

    def test_creates_gemini_embeddings_with_configured_model_and_key(
        self, mocker, monkeypatch
    ):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-test-embedding")
        gemini_embeddings = mocker.patch(
            "app.rag.embeddings.GoogleGenerativeAIEmbeddings"
        )

        result = get_embeddings()

        gemini_embeddings.assert_called_once_with(
            model="gemini-test-embedding",
            google_api_key="test-gemini-key",
        )
        assert result is gemini_embeddings.return_value

    def test_gemini_embedding_model_has_a_documented_default(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)

        assert get_embedding_config() == {
            "provider": "gemini",
            "model": DEFAULT_GEMINI_EMBEDDING_MODEL,
        }

    def test_gemini_embeddings_require_their_api_key(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"):
            get_embeddings()

    def test_unknown_embedding_provider_is_rejected(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "unsupported")

        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            get_embedding_config()
