"""Unit and live-API tests for app.agents.planner.

get_tool_decision(question: str) -> ToolDecision is the seam under test.
Most tests mock the LLM boundary (app.agents.planner.llm) so they run
without network access or API cost. The `requires_api` class exercises
the real OpenAI-backed planner and is skipped unless OPENAI_API_KEY is
set, since it is a probabilistic regression test (see below) rather
than a deterministic unit test.
"""
import os
from collections import Counter

import pytest

from app.agents.planner import get_tool_decision, planner_node
from app.contracts.agent import AgentState


def make_structured_llm(mocker, tool="doc_retriever", reason="looked up docs", tool_input=None, usage_metadata=None):
    """Build a mock get_llm() replacement whose
    with_structured_output(..., include_raw=True) returns a
    {"raw": <AIMessage-like>, "parsed": <ToolDecision-like>} dict, matching
    LangChain's include_raw=True contract (needed to access usage_metadata,
    which is only present on the raw message, not the parsed model).
    """
    parsed = mocker.Mock(tool=tool, reason=reason, tool_input=tool_input or {})
    raw = mocker.Mock(usage_metadata=usage_metadata)
    mock_structured = mocker.Mock()
    mock_structured.invoke.return_value = {"raw": raw, "parsed": parsed}
    mock_llm = mocker.Mock()
    mock_llm.model_name = "gpt-5.4-mini"
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm, mock_structured


@pytest.mark.unit
class TestGetToolDecision:
    def test_builds_tool_options_from_the_registry_and_returns_structured_output(self, mocker):
        mock_llm, mock_structured = make_structured_llm(
            mocker, tool="doc_retriever", reason="looked up docs", tool_input={"query": "q"}
        )
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)

        result, usage = get_tool_decision("How does PaymentRetryService handle failed retries?")

        assert result.tool == "doc_retriever"
        mock_llm.with_structured_output.assert_called_once()
        mock_structured.invoke.assert_called_once()

    def test_returns_none_token_usage_when_the_provider_gives_no_usage_metadata(self, mocker):
        mock_llm, _ = make_structured_llm(mocker, usage_metadata=None)
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)

        _, usage = get_tool_decision("a question")

        assert usage is None

    def test_returns_token_usage_when_the_provider_gives_usage_metadata(self, mocker):
        mock_llm, _ = make_structured_llm(
            mocker,
            usage_metadata={"input_tokens": 200, "output_tokens": 15, "total_tokens": 215},
        )
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)

        _, usage = get_tool_decision("a question")

        assert usage == {"input_tokens": 200, "output_tokens": 15, "model": "gpt-5.4-mini"}


@pytest.mark.unit
class TestPlannerNodeLlmUsage:
    """Week 9: planner_node records one LLM call and its token usage into
    state.stage_llm_usage["planner"], mirroring the existing
    state.stage_timings["planner"] pattern."""

    def test_records_one_llm_call_and_token_usage(self, mocker):
        mock_llm, _ = make_structured_llm(
            mocker,
            usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        )
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)
        state = AgentState(user_input="a question", trace_id="trace-1")

        result = planner_node(state)

        assert result.stage_llm_usage["planner"]["llm_calls"] == 1
        assert result.stage_llm_usage["planner"]["token_usage"] == {
            "input_tokens": 100, "output_tokens": 20, "model": "gpt-5.4-mini"
        }

    def test_records_none_token_usage_when_the_provider_gives_none(self, mocker):
        mock_llm, _ = make_structured_llm(mocker, usage_metadata=None)
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)
        state = AgentState(user_input="a question", trace_id="trace-1")

        result = planner_node(state)

        assert result.stage_llm_usage["planner"]["llm_calls"] == 1
        assert result.stage_llm_usage["planner"]["token_usage"] is None


@pytest.mark.requires_api
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY")
class TestPlannerNamedServiceRouting:
    """Regression test for an intermittent planner misrouting bug.

    Found via evaluation/results/eval_2026-09-22_22-54-17.json: the
    question "How does PaymentRetryService handle failed retries?" was
    sometimes routed to "none" instead of "doc_retriever", since the
    planner prompt gave no guidance on questions naming a specific
    internal class/service, and PaymentRetryService's behavior is only
    knowable from internal docs, not general knowledge.

    This is a probabilistic misrouting (confirmed live: ~1 in 5-20 runs
    picked "none" before the fix to app/prompts/planner.txt and
    app/tools/registry.py's "none" description), not a deterministic
    branch bug, so the regression test samples the real planner
    repeatedly rather than asserting a single call. Per the
    diagnosing-bugs skill's non-deterministic-bug guidance: the goal is
    a high reproduction rate for the failure, then a threshold the fix
    must clear, not a single flaky assertion.

    Confirmed live before the fix: 1/5 and 1/20 samples selected "none".
    Confirmed live after the fix: 20/20 and 20/20 samples selected
    "doc_retriever" across two separate runs.
    """

    def test_named_internal_service_question_routes_to_doc_retriever(self):
        question = "How does PaymentRetryService handle failed retries?"
        samples = 20

        results = Counter(
            get_tool_decision(question)[0].tool for _ in range(samples)
        )

        # Allow a small margin for irreducible LLM stochasticity while
        # still catching the misrouting bug, which surfaced at a much
        # higher flake rate (up to 1 in 5) before the prompt fix.
        assert results["doc_retriever"] >= samples - 1, (
            f"Expected doc_retriever in at least {samples - 1}/{samples} runs, got: {results}"
        )
