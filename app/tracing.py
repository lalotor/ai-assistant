import structlog
from app.contracts.trace import ExecutionTrace, StageEvent
from app.utils.util import calculate_duration_ms

logger = structlog.get_logger()


def build_execution_trace(state: dict) -> ExecutionTrace:
    """Build an execution trace from the final state of the workflow."""

    logger.info(
        "building_execution_trace", 
        trace_id=state["trace_id"]
    )

    planner_started_at = state.get("stage_timings", {}).get("planner", {}).get("started_at", "")
    planner_ended_at = state.get("stage_timings", {}).get("planner", {}).get("ended_at", "")
    worker_started_at = state.get("stage_timings", {}).get("worker", {}).get("started_at", "")
    worker_ended_at = state.get("stage_timings", {}).get("worker", {}).get("ended_at", "")
    reviewer_started_at = state.get("stage_timings", {}).get("reviewer", {}).get("started_at", "")
    reviewer_ended_at = state.get("stage_timings", {}).get("reviewer", {}).get("ended_at", "")

    planner_event = StageEvent(
        stage="planner",
        started_at=planner_started_at,
        ended_at=planner_ended_at,
        duration_ms=calculate_duration_ms(planner_started_at, planner_ended_at),
        input_snapshot={"user_input": state["user_input"]},
        output_snapshot={
            "plan": state["plan"],
            "selected_tool": state["selected_tool"],
            "tool_input": state["tool_input"],
        },
    )

    worker_event = StageEvent(
        stage="worker",
        started_at=worker_started_at,
        ended_at=worker_ended_at,
        duration_ms=calculate_duration_ms(worker_started_at, worker_ended_at),
        input_snapshot={
            "selected_tool": state["selected_tool"],
            "tool_input": state["tool_input"]
        },
        output_snapshot={
            "tool_output": state["tool_output"],
            "draft_answer": state["draft_answer"]
        },
    )

    reviewer_event = StageEvent(
        stage="reviewer",
        started_at=reviewer_started_at,
        ended_at=reviewer_ended_at,
        duration_ms=calculate_duration_ms(reviewer_started_at, reviewer_ended_at),
        input_snapshot={
            "user_input": state["user_input"],
            "draft_answer": state["draft_answer"]
        },
        output_snapshot={
            "final_answer": state["final_answer"],
            "review_feedback": state["review_feedback"]
        },
    )

    return ExecutionTrace(
        trace_id=state["trace_id"],
        started_at=planner_started_at,
        ended_at=reviewer_ended_at,
        duration_ms=calculate_duration_ms(planner_started_at, reviewer_ended_at),
        planner_events=[planner_event],
        worker_events=[worker_event],
        reviewer_events=[reviewer_event],
        retrieval_trace=state.get("retrieval_trace", None),
        final_answer=state.get("final_answer", ""),
    )
