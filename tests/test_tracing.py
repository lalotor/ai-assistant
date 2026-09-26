"""Unit tests for the build_execution_trace() seam in app.tracing.

build_execution_trace(state) -> ExecutionTrace is the module's only public
interface and its only real caller (app.runtime.assistant_runtime). The
internal per-stage StageEvent construction is an implementation detail
reached only through this seam.
"""
from datetime import datetime

import pytest

from app.tracing import build_execution_trace


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
