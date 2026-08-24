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


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""

    status: str = Field(description="'ok' when the service is healthy.")
    runtime_initialized: bool = Field(
        description="True when AssistantRuntime.setup() has completed."
    )
