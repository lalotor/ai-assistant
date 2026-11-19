import os
from typing import Any, Optional
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


LLM_MAX_RETRIES = 2
LLM_REQUEST_TIMEOUT_SECONDS = 30
_DEFAULT_MODELS = {
    "openai": "gpt-5.4-mini",
    "gemini": "gemini-3.5-flash-lite",
    "groq": "openai/gpt-oss-20b",
}


def get_llm(
    model: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """Create the configured chat model, preserving OpenAI as the default."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model_name = model or os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(provider)
    if model_name is None:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=0 if temperature is None else temperature,
            max_retries=LLM_MAX_RETRIES,
            request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        return ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            max_retries=LLM_MAX_RETRIES,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
            **({"temperature": temperature} if temperature is not None else {}),
        )
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0 if temperature is None else temperature,
            max_retries=LLM_MAX_RETRIES,
            request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def get_model_name(model: BaseChatModel) -> str:
    """Return a provider-neutral model identifier for trace metadata."""
    model_name = getattr(model, "model_name", None) or getattr(model, "model", None)
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("Configured chat model does not expose a model identifier.")
    return model_name


def get_structured_output(
    model: BaseChatModel,
    schema: type[BaseModel],
    *,
    include_raw: bool = False,
) -> Runnable[Any, Any]:
    """Create structured output using the configured provider's compatible mode."""
    options: dict[str, Any] = {"include_raw": include_raw}
    if os.getenv("LLM_PROVIDER", "openai").lower() == "groq":
        options["method"] = "function_calling"
    return model.with_structured_output(schema, **options)


def extract_model_usage(ai_message: Any, model: BaseChatModel) -> Optional[dict]:
    """Extract usage only when present and resolve the provider's model field."""
    if getattr(ai_message, "usage_metadata", None) is None:
        return None
    return extract_usage(ai_message, model_name=get_model_name(model))


def extract_usage(ai_message: Any, model_name: str) -> Optional[dict]:
    """Extract token usage from an AIMessage's usage_metadata for cost/perf
    tracing (Week 9).

    Returns None (rather than a dict of zeros) when the provider didn't
    return usage metadata at all, so callers can distinguish "no usage
    data available" from "zero tokens used" - the two mean very different
    things for a cost report.
    """
    usage = getattr(ai_message, "usage_metadata", None)
    if usage is None:
        return None

    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "model": model_name,
    }
