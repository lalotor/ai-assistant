"""Unit tests for app.utils.llm's extract_usage() seam.

extract_usage(ai_message, model_name) -> dict | None is the shared helper
every LLM-calling site (planner, reviewer, code_explainer,
architecture_advisor, doc_retriever's reranking step) uses to turn an
AIMessage's usage_metadata into the {"input_tokens", "output_tokens",
"model"} shape stored on StageEvent.token_usage (Week 9: cost/perf
tracing, not correctness data).
"""
import pytest

from app.utils.llm import extract_usage


class FakeAIMessage:
    def __init__(self, usage_metadata=None):
        self.usage_metadata = usage_metadata


@pytest.mark.unit
class TestExtractUsage:
    def test_extracts_input_and_output_tokens_with_model_name(self):
        message = FakeAIMessage(usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150})

        usage = extract_usage(message, model_name="gpt-5.4-mini")

        assert usage == {"input_tokens": 120, "output_tokens": 30, "model": "gpt-5.4-mini"}

    def test_returns_none_when_usage_metadata_is_absent(self):
        """None (not zeros) is the honest signal that the provider returned
        no usage data at all - a token report must be able to tell that
        apart from "this call genuinely used zero tokens"."""
        message = FakeAIMessage(usage_metadata=None)

        assert extract_usage(message, model_name="gpt-5.4-mini") is None

    def test_returns_none_when_the_message_has_no_usage_metadata_attribute(self):
        """Defensive: some message-like objects (e.g. a bare Mock without
        the attribute configured) won't even have the attribute."""
        class BareObject:
            pass

        assert extract_usage(BareObject(), model_name="gpt-5.4-mini") is None

    def test_defaults_missing_token_fields_to_zero(self):
        message = FakeAIMessage(usage_metadata={})

        usage = extract_usage(message, model_name="gpt-5.4-mini")

        assert usage == {"input_tokens": 0, "output_tokens": 0, "model": "gpt-5.4-mini"}
