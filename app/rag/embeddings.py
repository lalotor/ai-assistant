import os

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings


DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-2-preview"
DEFAULT_LOCAL_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_embedding_config() -> dict[str, str]:
    """Return the provider and model that define the vector representation."""
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if provider == "openai":
        return {
            "provider": provider,
            "model": DEFAULT_OPENAI_EMBEDDING_MODEL,
        }
    if provider == "gemini":
        return {
            "provider": provider,
            "model": os.getenv("GEMINI_EMBEDDING_MODEL")
            or DEFAULT_GEMINI_EMBEDDING_MODEL,
        }
    if provider == "local":
        return {
            "provider": provider,
            "model": os.getenv("LOCAL_EMBEDDING_MODEL")
            or DEFAULT_LOCAL_EMBEDDING_MODEL,
        }

    raise ValueError(f"Unsupported embedding provider: {provider}")


def get_embeddings():
    """Create the configured embedding model."""
    config = get_embedding_config()
    if config["provider"] == "openai":
        return OpenAIEmbeddings(model=config["model"])
    if config["provider"] == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini."
            )
        return GoogleGenerativeAIEmbeddings(
            model=config["model"],
            google_api_key=api_key,
        )
    if config["provider"] == "local":
        return HuggingFaceEmbeddings(
            model_name=config["model"],
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    raise ValueError(f"Unsupported embedding provider: {config['provider']}")
