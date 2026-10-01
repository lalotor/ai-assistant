from typing import Any, Optional
from langchain_openai import ChatOpenAI


def get_llm(model="gpt-5.4-mini", temperature=0):
    return ChatOpenAI(model=model, temperature=temperature)


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
