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

    planner_event = _build_stage_event(
        state,
        "planner",
        input_snapshot={"user_input": state["user_input"]},
        output_snapshot={
            "plan": state["plan"],
            "selected_tool": state["selected_tool"],
            "tool_input": state["tool_input"],
        },
    )

    worker_event = _build_stage_event(
        state,
        "worker",
        input_snapshot={
            "selected_tool": state["selected_tool"],
            "tool_input": state["tool_input"]
        },
        output_snapshot={
            "tool_output": state["tool_output"],
            "draft_answer": state["draft_answer"]
        },
    )

    reviewer_event = _build_stage_event(
        state,
        "reviewer",
        input_snapshot={
            "user_input": state["user_input"],
            "draft_answer": state["draft_answer"]
        },
        output_snapshot={
            "final_answer": state["final_answer"],
            "review_feedback": state["review_feedback"]
        },
    )

    overall_duration_ms = (
        calculate_duration_ms(planner_event.started_at, reviewer_event.ended_at)
        if planner_event.started_at is not None and reviewer_event.ended_at is not None
        else None
    )

    return ExecutionTrace(
        trace_id=state["trace_id"],
        started_at=planner_event.started_at,
        ended_at=reviewer_event.ended_at,
        duration_ms=overall_duration_ms,
        planner_events=[planner_event],
        worker_events=[worker_event],
        reviewer_events=[reviewer_event],
        retrieval_trace=state.get("retrieval_trace", None),
        final_answer=state.get("final_answer", ""),
    )


def _build_stage_event(
    state: dict,
    stage: str,
    input_snapshot: dict,
    output_snapshot: dict,
) -> StageEvent:
    """Build a StageEvent for one pipeline stage, looking up its timing from
    state["stage_timings"][stage] and its LLM usage from
    state["stage_llm_usage"][stage].

    If the stage's timing is missing entirely (e.g. stage_timings itself is
    absent, or the stage never ran), started_at/ended_at/duration_ms are
    None rather than empty strings, since ("" - "") is not a valid datetime
    subtraction and would raise.

    If the stage's LLM usage is missing (e.g. an older trace, or a stage
    that made no LLM calls), llm_calls defaults to 0 and token_usage to
    None rather than raising - usage tracking is a performance/cost
    metric, not a correctness field, so its absence must never break
    trace assembly.
    """
    timing = state.get("stage_timings", {}).get(stage)
    started_at = timing.get("started_at") if timing else None
    ended_at = timing.get("ended_at") if timing else None

    duration_ms = (
        calculate_duration_ms(started_at, ended_at)
        if started_at is not None and ended_at is not None
        else None
    )

    usage = state.get("stage_llm_usage", {}).get(stage)
    llm_calls = usage.get("llm_calls", 0) if usage else 0
    token_usage = usage.get("token_usage") if usage else None

    return StageEvent(
        stage=stage,
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        input_snapshot=input_snapshot,
        output_snapshot=output_snapshot,
        llm_calls=llm_calls,
        token_usage=token_usage,
    )
