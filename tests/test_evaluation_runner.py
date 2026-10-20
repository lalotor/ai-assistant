"""Unit tests for the classify_failure() seam in evaluation.runner.

classify_failure(item, response, score, score_sources) -> str | None is
the module's public failure-classification interface, called only from
run_evaluation() for items that already failed the score >= 0.5 pass
threshold. These tests verify that contract directly.

Note: evaluation.runner performs environment validation and logging
configuration at import time (by design, per its module docstring, so
all initialisation is centralised). This requires a valid .env to be
present, matching how the module is used in practice (via
`python -m evaluation.runner`).
"""
import subprocess

import pytest
from structlog.testing import capture_logs

from app.contracts.response import QueryResponse
from evaluation.runner import ask_assistant, classify_failure, score_keywords


def make_response(**overrides) -> QueryResponse:
    defaults = dict(
        user_input="q",
        plan="p",
        selected_tool="doc_retriever",
        tool_input={},
        tool_output="Some tool output",
        draft_answer="draft",
        final_answer="Some tool output",
        review_feedback="fb",
        retrieved_sources=[],
        execution_trace=None,
    )
    defaults.update(overrides)
    return QueryResponse(**defaults)


class _FakeTrace:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms


@pytest.mark.unit
class TestClassifyFailure:
    def test_returns_none_for_a_passing_score_even_if_slow(self):
        """Regression test: classify_failure previously checked
        duration_ms > slow_execution_threshold before checking whether the
        item actually failed (score >= 0.5), so a passing, high-quality,
        merely-slow answer was mislabeled "slow_execution" in the output
        even though its status was "pass". A failure classifier should
        never assign a failure type to a non-failing item."""
        response = make_response(execution_trace=_FakeTrace(duration_ms=999_999))
        item = {"category": "doc_retriever"}

        result = classify_failure(item, response, score=1.0, score_sources=1.0)

        assert result is None

    def test_classifies_slow_execution_for_a_failing_slow_item(self):
        response = make_response(execution_trace=_FakeTrace(duration_ms=999_999))
        item = {"category": "doc_retriever"}

        result = classify_failure(item, response, score=0.0, score_sources=0.0)

        assert result == "slow_execution"

    def test_classifies_tool_failure_when_tool_output_contains_error(self):
        response = make_response(
            final_answer="Error executing doc_retriever: boom",
            execution_trace=_FakeTrace(duration_ms=100),
        )
        item = {"category": "doc_retriever"}

        result = classify_failure(item, response, score=0.0, score_sources=0.0)

        assert result == "tool_failure"

    def test_classifies_planner_failure_when_category_mismatches_selected_tool(self):
        response = make_response(
            selected_tool="architecture_advisor",
            final_answer="some answer",
            execution_trace=_FakeTrace(duration_ms=100),
        )
        item = {"category": "doc_retriever"}

        result = classify_failure(item, response, score=0.0, score_sources=0.0)

        assert result == "planner_failure"

    def test_classifies_missing_context_when_expected_sources_do_not_exist(self):
        response = make_response(
            final_answer="some answer",
            execution_trace=_FakeTrace(duration_ms=100),
        )
        item = {
            "category": "doc_retriever",
            "expected_sources": ["definitely/does/not/exist.py"],
        }

        result = classify_failure(item, response, score=0.0, score_sources=0.0)

        assert result == "missing_context"


@pytest.mark.unit
class TestScoreKeywords:
    def test_accepts_explicit_phrasing_alternatives_for_required_concepts(self):
        answer = (
            "Retry up to 3 times with exponential backoff, then move the task "
            "to the dead letter queue."
        )
        groups = {
            "retry_count": ["retry_count", "retry up to 3 times", "up to 3 times"],
            "backoff": ["exponential backoff"],
            "retry_limit": ["max_retries", "maximum retries", "retry limit"],
            "dead_letter_queue": ["dead-letter queue", "dead letter queue"],
        }

        result = score_keywords(answer, expected_keyword_groups=groups)

        assert result["matched_keyword_groups"] == [
            "retry_count",
            "backoff",
            "dead_letter_queue",
        ]
        assert result["score"] == 0.75

    def test_preserves_legacy_exact_keyword_scoring(self):
        result = score_keywords("The answer uses alpha.", expected_keywords=["alpha", "beta"])

        assert result["matched_keywords"] == ["alpha"]
        assert result["score"] == 0.5


@pytest.mark.unit
class TestAskAssistant:
    def test_timeout_does_not_log_or_raise_with_question_content(self, mocker):
        secret = "evaluation-private-needle-508c"
        mocker.patch(
            "evaluation.runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="main.py", timeout=1),
        )

        with capture_logs() as logs:
            with pytest.raises(TimeoutError) as exc_info:
                ask_assistant(secret, timeout=1)

        assert secret not in repr(logs)
        assert secret not in str(exc_info.value)
