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

from app.agents.planner import get_tool_decision


@pytest.mark.unit
class TestGetToolDecision:
    def test_builds_tool_options_from_the_registry_and_returns_structured_output(self, mocker):
        mock_structured = mocker.Mock()
        mock_structured.invoke.return_value = mocker.Mock(
            tool="doc_retriever", reason="looked up docs", tool_input={"query": "q"}
        )
        mock_llm = mocker.Mock()
        mock_llm.with_structured_output.return_value = mock_structured
        mocker.patch("app.agents.planner.get_llm", return_value=mock_llm)

        result = get_tool_decision("How does PaymentRetryService handle failed retries?")

        assert result.tool == "doc_retriever"
        mock_llm.with_structured_output.assert_called_once()
        mock_structured.invoke.assert_called_once()


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
            get_tool_decision(question).tool for _ in range(samples)
        )

        # Allow a small margin for irreducible LLM stochasticity while
        # still catching the misrouting bug, which surfaced at a much
        # higher flake rate (up to 1 in 5) before the prompt fix.
        assert results["doc_retriever"] >= samples - 1, (
            f"Expected doc_retriever in at least {samples - 1}/{samples} runs, got: {results}"
        )
