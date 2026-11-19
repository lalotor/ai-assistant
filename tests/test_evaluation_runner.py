"""Unit tests for the classify_failure() seam in evaluation.runner.

classify_failure(item, response, score, score_sources) -> str | None is
the module's public failure-classification interface, called only from
run_evaluation() for items that already failed the score >= 0.5 pass
threshold. These tests verify that contract directly.

The runner is import-safe so its public evaluation functions can be reused
by the application runtime. CLI logging and environment validation are
configured when `python -m evaluation.runner` starts.
"""
import json
import subprocess

import pytest
from structlog.testing import capture_logs

from app.contracts.response import QueryResponse
from evaluation.runner import (
    ask_assistant,
    classify_failure,
    run_evaluation,
    score_keywords,
)


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

    @pytest.mark.parametrize(
        ("revision_enabled", "expect_flag"),
        [(False, False), (True, True)],
    )
    def test_adds_the_revision_flag_only_when_enabled(
        self, mocker, revision_enabled, expect_flag
    ):
        completed = mocker.Mock(
            returncode=0,
            stdout=json.dumps(make_response().to_dict()),
            stderr="",
        )
        run = mocker.patch("evaluation.runner.subprocess.run", return_value=completed)

        ask_assistant("q", timeout=1, revision_enabled=revision_enabled)

        command = run.call_args.args[0]
        assert ("--revision" in command) is expect_flag


@pytest.mark.unit
class TestRunEvaluation:
    def test_saves_progress_to_the_requested_results_file(self, mocker, tmp_path):
        dataset = tmp_path / "dataset.json"
        dataset.write_text(
            json.dumps([{"question": "What is X?", "expected_keywords": ["x"]}]),
            encoding="utf-8",
        )
        output = tmp_path / "results" / "evaluation.json"
        mocker.patch(
            "evaluation.runner.ask_assistant",
            side_effect=RuntimeError("private provider details"),
        )

        results = run_evaluation(str(dataset), results_file=str(output))

        saved = json.loads(output.read_text(encoding="utf-8"))
        assert results[0]["status"] == "error"
        assert results[0]["error_type"] == "RuntimeError"
        assert saved["summary"]["total_questions"] == 1
        assert saved["results"][0]["error"] == "private provider details"
