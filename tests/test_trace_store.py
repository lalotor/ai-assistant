from datetime import datetime, timedelta, timezone

import pytest

from app.contracts.trace import ExecutionTrace
from app.trace_store import TraceStore


def make_trace(trace_id: str) -> ExecutionTrace:
    return ExecutionTrace(
        trace_id=trace_id,
        started_at=None,
        ended_at=None,
        duration_ms=12.5,
        planner_events=[],
        worker_events=[],
        reviewer_events=[],
        retrieval_trace=None,
        final_answer="The answer is grounded in the saved source.",
    )


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 11, 18, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.current


@pytest.mark.unit
class TestTraceStore:
    def test_persisted_trace_can_be_retrieved_with_its_content(self, tmp_path):
        store = TraceStore(tmp_path / "traces.sqlite3")
        trace = make_trace("trace-123")

        store.save(trace)

        assert store.get("trace-123") == trace.to_dict()
        assert store.get("unknown-trace") is None

    def test_expired_traces_are_hidden_and_pruned_on_the_next_write(self, tmp_path):
        clock = MutableClock()
        store = TraceStore(tmp_path / "traces.sqlite3", clock=clock)
        store.save(make_trace("expired-trace"))

        clock.current += timedelta(days=8)
        assert store.get("expired-trace") is None

        store.save(make_trace("current-trace"))

        assert store.get("expired-trace") is None
        assert store.get("current-trace") is not None
