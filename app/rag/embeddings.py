import os
from langchain_openai import OpenAIEmbeddings

def get_embeddings():
    """Factory function to get the appropriate embeddings class based on environment variable."""
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")

    raise ValueError(f"Unsupported embedding provider: {provider}")
