"""Unit tests for the build_execution_trace() seam in app.tracing.

build_execution_trace(state) -> ExecutionTrace is the module's only public
interface and its only real caller (app.runtime.assistant_runtime). The
internal per-stage StageEvent construction is an implementation detail
reached only through this seam.
"""
from datetime import datetime

import pytest

from app.contracts.trace import RetrievalTrace
from app.tracing import build_execution_trace, build_failed_execution_trace


def make_full_state(**overrides) -> dict:
    """A complete, valid final graph state with all three stages timed."""
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    t1 = datetime(2026, 1, 1, 12, 0, 1)
    t2 = datetime(2026, 1, 1, 12, 0, 2)
    t3 = datetime(2026, 1, 1, 12, 0, 3)

    state = {
        "trace_id": "trace-123",
        "user_input": "what is X?",
        "plan": "use doc_retriever",
        "selected_tool": "doc_retriever",
        "tool_input": {"query": "what is X?"},
        "tool_output": "some context",
        "draft_answer": "Tool result:\nsome context",
        "final_answer": "X is ...",
        "review_feedback": "looks good",
        "retrieval_trace": None,
        "stage_timings": {
            "planner": {"started_at": t0, "ended_at": t1},
            "worker": {"started_at": t1, "ended_at": t2},
            "reviewer": {"started_at": t2, "ended_at": t3},
        },
    }
    state.update(overrides)
    return state


@pytest.mark.unit
class TestBuildExecutionTrace:
    def test_marks_normal_execution_as_success(self):
        trace = build_execution_trace(make_full_state(selected_tool="none"))

        assert trace.outcome == "success"
        assert trace.to_dict()["outcome"] == "success"

    def test_marks_retrieval_fallback_as_degraded(self):
        trace = build_execution_trace(
            make_full_state(
                retrieval_trace=RetrievalTrace(
                    query="what is X?",
                    vector_search_status="failed",
                    keyword_search_status="succeeded",
                    fallback_used=True,
                ),
                retrieved_sources=["reliability.md"],
            )
        )

        assert trace.outcome == "degraded"

    def test_marks_empty_document_retrieval_abstention_as_degraded(self):
        trace = build_execution_trace(
            make_full_state(
                retrieval_trace=RetrievalTrace(
                    query="what is X?",
                    vector_search_status="succeeded",
                    keyword_search_status="succeeded",
                ),
                retrieved_sources=[],
                final_answer="I couldn't find relevant documentation.",
            )
        )

        assert trace.outcome == "degraded"

    def test_builds_one_stage_event_per_stage_with_correct_snapshots(self):
        state = make_full_state()

        trace = build_execution_trace(state)

        assert trace.trace_id == "trace-123"
        assert len(trace.planner_events) == 1
        assert len(trace.worker_events) == 1
        assert len(trace.reviewer_events) == 1

        planner_event = trace.planner_events[0]
        assert planner_event.stage == "planner"
        assert planner_event.input_snapshot == {"user_input": "what is X?"}
        assert planner_event.output_snapshot == {
            "plan": "use doc_retriever",
            "selected_tool": "doc_retriever",
            "tool_input": {"query": "what is X?"},
        }

        worker_event = trace.worker_events[0]
        assert worker_event.output_snapshot == {
            "tool_output": "some context",
            "draft_answer": "Tool result:\nsome context",
        }

        reviewer_event = trace.reviewer_events[0]
        assert reviewer_event.output_snapshot == {
            "final_answer": "X is ...",
            "review_feedback": "looks good",
            "review_decision": None,
        }

    def test_computes_stage_durations_in_milliseconds(self):
        state = make_full_state()

        trace = build_execution_trace(state)

        assert trace.planner_events[0].duration_ms == 1000.0
        assert trace.worker_events[0].duration_ms == 1000.0
        assert trace.reviewer_events[0].duration_ms == 1000.0

    def test_overall_trace_spans_planner_start_to_reviewer_end(self):
        state = make_full_state()

        trace = build_execution_trace(state)

        assert trace.started_at == state["stage_timings"]["planner"]["started_at"]
        assert trace.ended_at == state["stage_timings"]["reviewer"]["ended_at"]
        assert trace.duration_ms == 3000.0

    def test_missing_stage_timings_does_not_raise(self):
        """Regression test: stage_timings defaulting to {} previously produced
        empty-string timestamps ("" - "" is invalid for datetime subtraction),
        which would raise instead of degrading gracefully."""
        state = make_full_state()
        del state["stage_timings"]

        trace = build_execution_trace(state)

        assert trace.planner_events[0].started_at is None
        assert trace.planner_events[0].ended_at is None
        assert trace.planner_events[0].duration_ms is None

    def test_partial_stage_timings_does_not_raise(self):
        """Only some stages timed (e.g. an earlier failure) must not raise."""
        state = make_full_state()
        del state["stage_timings"]["reviewer"]

        trace = build_execution_trace(state)

        assert trace.reviewer_events[0].started_at is None
        assert trace.reviewer_events[0].duration_ms is None
        # Stages that do have timings are unaffected
        assert trace.planner_events[0].duration_ms == 1000.0

    def test_passes_through_retrieval_trace_and_final_answer(self):
        state = make_full_state(retrieval_trace="a-fake-retrieval-trace")

        trace = build_execution_trace(state)

        assert trace.retrieval_trace == "a-fake-retrieval-trace"
        assert trace.final_answer == "X is ..."


@pytest.mark.unit
class TestBuildExecutionTraceLlmUsage:
    """Week 9: llm_calls/token_usage are performance/cost metrics, sourced
    from state["stage_llm_usage"][stage] the same way timings are sourced
    from state["stage_timings"][stage]."""

    def test_reads_llm_calls_and_token_usage_per_stage(self):
        state = make_full_state(stage_llm_usage={
            "planner": {
                "llm_calls": 1,
                "token_usage": {"input_tokens": 100, "output_tokens": 20, "model": "gpt-5.4-mini"},
            },
            "worker": {
                "llm_calls": 2,
                "token_usage": {"input_tokens": 500, "output_tokens": 80, "model": "gpt-5.4-mini"},
            },
            "reviewer": {
                "llm_calls": 1,
                "token_usage": {"input_tokens": 150, "output_tokens": 40, "model": "gpt-5.4-mini"},
            },
        })

        trace = build_execution_trace(state)

        assert trace.planner_events[0].llm_calls == 1
        assert trace.planner_events[0].token_usage == {
            "input_tokens": 100, "output_tokens": 20, "model": "gpt-5.4-mini"
        }
        # Worker's llm_calls is 2 when doc_retriever's reranking step ran,
        # not 1 - this is the whole point of tracking it separately from a
        # flat "one call per stage" assumption.
        assert trace.worker_events[0].llm_calls == 2
        assert trace.reviewer_events[0].llm_calls == 1

    def test_missing_stage_llm_usage_defaults_to_zero_calls_and_no_token_usage(self):
        """A stage with no recorded usage (e.g. an older trace, or a stage
        that made no LLM calls, like the \"none\" tool) must not raise, and
        must not be silently confused with \"one call happened\"."""
        state = make_full_state()
        assert "stage_llm_usage" not in state

        trace = build_execution_trace(state)

        assert trace.planner_events[0].llm_calls == 0
        assert trace.planner_events[0].token_usage is None
        assert trace.worker_events[0].llm_calls == 0
        assert trace.reviewer_events[0].llm_calls == 0

    def test_partial_stage_llm_usage_only_affects_the_stages_present(self):
        state = make_full_state(stage_llm_usage={
            "planner": {"llm_calls": 1, "token_usage": {"input_tokens": 100, "output_tokens": 20, "model": "gpt-5.4-mini"}},
        })

        trace = build_execution_trace(state)

        assert trace.planner_events[0].llm_calls == 1
        assert trace.worker_events[0].llm_calls == 0
        assert trace.worker_events[0].token_usage is None


def make_revision_state(**overrides) -> dict:
    """A complete state for one approved revision: initial review, revision,
    and final review."""
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    t1 = datetime(2026, 1, 1, 12, 0, 1)
    t2 = datetime(2026, 1, 1, 12, 0, 2)
    t3 = datetime(2026, 1, 1, 12, 0, 3)
    t4 = datetime(2026, 1, 1, 12, 0, 4)
    t5 = datetime(2026, 1, 1, 12, 0, 5)

    state = make_full_state(
        initial_draft_answer="Tool result:\ninitial draft",
        draft_answer="Tool result:\nrevised draft",
        final_answer="revised final answer",
        initial_review_decision="revise",
        initial_review_feedback="Add the missing detail.",
        review_decision="approve",
        review_feedback="The revised answer is grounded.",
        revision_feedback="Add the missing detail.",
        revision_count=1,
        review_outcome="revised",
        stage_timings={
            "planner": {"started_at": t0, "ended_at": t1},
            "worker": {"started_at": t1, "ended_at": t2},
            "reviewer": {"started_at": t2, "ended_at": t3},
            "revision": {"started_at": t3, "ended_at": t4},
            "reviewer_final": {"started_at": t4, "ended_at": t5},
        },
        stage_llm_usage={
            "planner": {"llm_calls": 1, "token_usage": None},
            "worker": {"llm_calls": 1, "token_usage": None},
            "reviewer": {"llm_calls": 1, "token_usage": None},
            "revision": {"llm_calls": 1, "token_usage": None},
            "reviewer_final": {"llm_calls": 1, "token_usage": None},
        },
    )
    state.update(overrides)
    return state


@pytest.mark.unit
class TestRevisionTrace:
    def test_records_both_reviewer_passes_and_the_revision_event(self):
        trace = build_execution_trace(make_revision_state())

        assert [event.stage for event in trace.reviewer_events] == [
            "reviewer",
            "reviewer_final",
        ]
        assert len(trace.revision_events) == 1
        assert trace.revision_events[0].stage == "revision"
        assert trace.revision_events[0].output_snapshot == {
            "draft_answer": "Tool result:\nrevised draft",
        }
        assert trace.review_trace.initial_decision == "revise"
        assert trace.review_trace.final_decision == "approve"
        assert trace.review_trace.revision_attempted is True
        assert trace.review_trace.revision_count == 1
        assert trace.review_trace.outcome == "revised"
        assert trace.outcome == "success"
        assert trace.duration_ms == 5000.0

    def test_initial_review_uses_the_initial_draft_and_final_review_uses_the_revision(self):
        trace = build_execution_trace(make_revision_state())

        assert trace.reviewer_events[0].input_snapshot["draft_answer"] == (
            "Tool result:\ninitial draft"
        )
        assert trace.reviewer_events[0].output_snapshot == {
            "final_answer": None,
            "review_feedback": "Add the missing detail.",
            "review_decision": "revise",
        }
        assert trace.reviewer_events[1].input_snapshot["draft_answer"] == (
            "Tool result:\nrevised draft"
        )
        assert trace.reviewer_events[1].output_snapshot == {
            "final_answer": "revised final answer",
            "review_feedback": "The revised answer is grounded.",
            "review_decision": "approve",
        }

    def test_revision_and_final_review_carry_their_own_llm_usage(self):
        trace = build_execution_trace(make_revision_state())

        assert trace.reviewer_events[0].llm_calls == 1
        assert trace.revision_events[0].llm_calls == 1
        assert trace.reviewer_events[1].llm_calls == 1

    @pytest.mark.parametrize("outcome", ["abstained", "budget_exhausted"])
    def test_marks_abstention_and_budget_exhaustion_as_degraded(self, outcome):
        trace = build_execution_trace(
            make_full_state(review_outcome=outcome, review_decision="abstain")
        )

        assert trace.outcome == "degraded"

    def test_revision_skipped_in_single_pass_mode_remains_successful(self):
        trace = build_execution_trace(
            make_full_state(
                review_outcome="revision_skipped",
                review_decision="revise",
            )
        )

        assert trace.outcome == "success"

    def test_review_trace_and_revision_events_survive_from_dict(self):
        from app.contracts.trace import ExecutionTrace

        trace = build_execution_trace(make_revision_state())
        restored = ExecutionTrace.from_dict(trace.to_dict())

        assert len(restored.revision_events) == 1
        assert restored.review_trace.initial_decision == "revise"
        assert restored.review_trace.final_decision == "approve"


@pytest.mark.unit
class TestFailedTraceNewStages:
    @pytest.mark.parametrize(
        "failed_stage,failure_category",
        [
            ("revision", "operation_timeout"),
            ("reviewer_final", "reviewer_failure"),
        ],
    )
    def test_builds_content_free_events_for_revision_and_final_review_failures(
        self,
        failed_stage,
        failure_category,
    ):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = datetime(2026, 1, 1, 12, 0, 1)
        t2 = datetime(2026, 1, 1, 12, 0, 2)
        t3 = datetime(2026, 1, 1, 12, 0, 3)
        t4 = datetime(2026, 1, 1, 12, 0, 4)
        stage_timings = {
            "planner": {"started_at": t0, "ended_at": t1},
            "worker": {"started_at": t1, "ended_at": t2},
            "reviewer": {"started_at": t2, "ended_at": t3},
            failed_stage: {"started_at": t3, "ended_at": t4},
        }

        trace = build_failed_execution_trace(
            trace_id="failed-trace",
            stage_timings=stage_timings,
            failed_stage=failed_stage,
            failure_category=failure_category,
            failure_type="TimeoutError",
            review_state={
                "initial_decision": "revise",
                "revision_attempted": True,
                "revision_count": 1 if failed_stage == "reviewer_final" else 0,
                "final_decision": None,
                "final_feedback": None,
                "outcome": None,
            },
        )

        assert trace.outcome == "failed"
        assert trace.failed_stage == failed_stage
        assert trace.failure_category == failure_category
        assert trace.final_answer == ""
        assert trace.duration_ms == 4000.0
        assert trace.review_trace.initial_decision == "revise"
        assert trace.review_trace.final_feedback is None
        assert trace.reviewer_events[0].input_snapshot == {}
        assert trace.reviewer_events[0].output_snapshot == {}

        if failed_stage == "revision":
            assert trace.revision_events[0].error == failure_category
            assert trace.revision_events[0].input_snapshot == {}
            assert len(trace.reviewer_events) == 1
        else:
            assert len(trace.reviewer_events) == 2
            assert trace.reviewer_events[1].error == failure_category
            assert trace.reviewer_events[1].input_snapshot == {}
