from pydantic import BaseModel, Field


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
    review_decision: str | None = Field(
        default=None,
        description="The reviewer's final decision: approve, revise, or abstain.",
    )
    revision_count: int = Field(
        default=0,
        description="Number of revisions attempted (0 or 1).",
    )
    review_outcome: str | None = Field(
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
