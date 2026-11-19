from typing import Any

from pydantic import BaseModel, Field

from app.contracts.review import ReviewDecision, ReviewOutcome


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------

class AskResponse(BaseModel):
    """Simplified response model for the /ask endpoint."""

    trace_id: str = Field(description="Unique ID for this execution.")
    answer: str = Field(description="The final answer produced by the assistant.")
    sources: list[str] | None = Field(
        default=None,
        description="Source files used during retrieval, if any.",
    )
    review_decision: ReviewDecision | None = Field(
        default=None,
        description="The reviewer's final decision: approve, revise, or abstain.",
    )
    revision_count: int = Field(
        default=0,
        description="Number of revisions attempted (0 or 1).",
    )
    review_outcome: ReviewOutcome | None = Field(
        default=None,
        description=(
            "Final review outcome: approved, revised, abstained, "
            "budget_exhausted, or revision_skipped."
        ),
    )


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""

    status: str = Field(description="'ok' when the service is healthy.")
    runtime_initialized: bool = Field(
        description="True when AssistantRuntime.setup() has completed."
    )


class TraceResponse(BaseModel):
    """Full persisted execution trace returned by the trace lookup endpoint."""

    trace_id: str = Field(description="The requested execution trace ID.")
    execution_trace: dict[str, Any] = Field(
        description="Full execution trace, including stage snapshots and retrieved content."
    )


class EvaluationResponse(BaseModel):
    """Aggregate and per-question results from a completed evaluation run."""

    dataset: str = Field(description="Built-in dataset used for this run.")
    revision_enabled: bool = Field(description="Whether bounded revision was enabled.")
    results_file: str = Field(description="Project-relative path to the saved raw results.")
    summary: dict[str, Any] = Field(description="Aggregate quality, latency, and usage metrics.")
    status_counts: dict[str, int] = Field(
        description="Count of per-question pass, fail, timeout, and error outcomes."
    )
    results: list[dict[str, Any]] = Field(
        description="Per-question evaluation results, including timing and usage data."
    )
