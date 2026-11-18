import structlog
from app.contracts.trace import ExecutionTrace, ReviewTrace, STAGE_NAMES, StageEvent
from app.utils.util import calculate_duration_ms

logger = structlog.get_logger()


def build_failed_execution_trace(
    trace_id: str,
    stage_timings: dict,
    failed_stage: str,
    failure_category: str,
    failure_type: str,
    review_state: dict | None = None,
) -> ExecutionTrace:
    """Build a content-free execution trace for a failed graph invocation.

    ``review_state`` carries only structured decisions/counts, never feedback
    or document content, so a failure after review can still show what the
    reviewer decided before the failing stage.
    """
    state = {
        "stage_timings": stage_timings,
        "stage_llm_usage": {},
    }
    events = {
        stage: _build_stage_event(state, stage, {}, {})
        for stage in STAGE_NAMES
    }
    if failed_stage not in events:
        events[failed_stage] = _build_stage_event(state, failed_stage, {}, {})
    events[failed_stage].error = failure_category

    reviewer_events = [events["reviewer"]]
    if _has_stage_timing(state, "reviewer_final"):
        reviewer_events.append(events["reviewer_final"])
    revision_events = (
        [events["revision"]] if _has_stage_timing(state, "revision") else []
    )

    started_at = events["planner"].started_at
    ended_at = events[failed_stage].ended_at
    duration_ms = (
        calculate_duration_ms(started_at, ended_at)
        if started_at is not None and ended_at is not None
        else None
    )

    review_trace = None
    if review_state is not None:
        review_trace = ReviewTrace(
            initial_decision=review_state.get("initial_decision"),
            revision_attempted=bool(review_state.get("revision_attempted")),
            revision_count=review_state.get("revision_count", 0),
            final_decision=review_state.get("final_decision"),
            final_feedback=None,
            outcome=review_state.get("outcome"),
        )

    return ExecutionTrace(
        trace_id=trace_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        planner_events=[events["planner"]],
        worker_events=[events["worker"]],
        reviewer_events=reviewer_events,
        retrieval_trace=None,
        final_answer="",
        revision_events=revision_events,
        review_trace=review_trace,
        outcome="failed",
        failed_stage=failed_stage,
        failure_category=failure_category,
        failure_type=failure_type,
    )


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

    reviewer_stages = [
        stage for stage in ("reviewer", "reviewer_final")
        if _has_stage_timing(state, stage)
    ] or ["reviewer"]
    has_final_review = "reviewer_final" in reviewer_stages

    reviewer_events = [
        _build_reviewer_event(state, stage, has_final_review=has_final_review)
        for stage in reviewer_stages
    ]

    revision_events = []
    if _has_stage_timing(state, "revision"):
        revision_events.append(
            _build_stage_event(
                state,
                "revision",
                input_snapshot={
                    "user_input": state["user_input"],
                    "selected_tool": state.get("selected_tool"),
                    "draft_answer": (
                        state.get("initial_draft_answer")
                        or state.get("draft_answer")
                    ),
                    "review_feedback": (
                        state.get("initial_review_feedback")
                        or state.get("revision_feedback")
                    ),
                },
                output_snapshot={
                    "draft_answer": state.get("draft_answer"),
                },
            )
        )

    final_reviewer_event = reviewer_events[-1]
    overall_duration_ms = (
        calculate_duration_ms(planner_event.started_at, final_reviewer_event.ended_at)
        if planner_event.started_at is not None and final_reviewer_event.ended_at is not None
        else None
    )
    retrieval_trace = state.get("retrieval_trace")
    retrieved_sources = state.get("retrieved_sources")
    degraded = bool(_trace_value(retrieval_trace, "fallback_used"))
    if (
        retrieval_trace is not None
        and state.get("selected_tool") == "doc_retriever"
        and not retrieved_sources
    ):
        degraded = True
    if state.get("review_outcome") in {"abstained", "budget_exhausted"}:
        degraded = True

    review_trace = _build_review_trace(state, has_final_review=has_final_review)

    return ExecutionTrace(
        trace_id=state["trace_id"],
        started_at=planner_event.started_at,
        ended_at=final_reviewer_event.ended_at,
        duration_ms=overall_duration_ms,
        planner_events=[planner_event],
        worker_events=[worker_event],
        reviewer_events=reviewer_events,
        retrieval_trace=retrieval_trace,
        final_answer=state.get("final_answer") or "",
        revision_events=revision_events,
        review_trace=review_trace,
        outcome="degraded" if degraded else "success",
    )


def _build_reviewer_event(
    state: dict,
    stage: str,
    *,
    has_final_review: bool,
) -> StageEvent:
    required_final = stage == "reviewer_final"
    if required_final:
        draft_answer = state.get("draft_answer")
        output_snapshot = {
            "final_answer": state.get("final_answer"),
            "review_feedback": state.get("review_feedback"),
            "review_decision": state.get("review_decision"),
        }
    else:
        draft_answer = state.get("initial_draft_answer") or state.get("draft_answer")
        output_snapshot = {
            "final_answer": None if has_final_review else state.get("final_answer"),
            "review_feedback": (
                state.get("initial_review_feedback")
                or (None if has_final_review else state.get("review_feedback"))
            ),
            "review_decision": (
                state.get("initial_review_decision")
                or (None if has_final_review else state.get("review_decision"))
            ),
        }

    return _build_stage_event(
        state,
        stage,
        input_snapshot={
            "user_input": state["user_input"],
            "draft_answer": draft_answer,
        },
        output_snapshot=output_snapshot,
    )


def _build_review_trace(state: dict, *, has_final_review: bool) -> ReviewTrace:
    initial_decision = state.get("initial_review_decision")
    initial_feedback = state.get("initial_review_feedback")
    if not has_final_review:
        initial_decision = initial_decision or state.get("review_decision")
        initial_feedback = initial_feedback or state.get("review_feedback")

    return ReviewTrace(
        initial_decision=initial_decision,
        initial_feedback=initial_feedback,
        revision_attempted=bool(state.get("revision_count", 0)),
        revision_count=state.get("revision_count", 0),
        final_decision=state.get("review_decision"),
        final_feedback=state.get("review_feedback"),
        outcome=state.get("review_outcome"),
    )


def _has_stage_timing(state: dict, stage: str) -> bool:
    return stage in (state.get("stage_timings") or {})


def _trace_value(retrieval_trace: object, field: str) -> object:
    if isinstance(retrieval_trace, dict):
        return retrieval_trace.get(field)
    return getattr(retrieval_trace, field, None)


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
