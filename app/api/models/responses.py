from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Trace sub-models (mirror app/contracts/trace.py as Pydantic for OpenAPI)
# ---------------------------------------------------------------------------

class RetrievalTraceModel(BaseModel):
    """Serialised view of a retrieval pipeline trace."""

    query: str
    vector_results_count: int | None = None
    keyword_results_count: int | None = None
    merged_count: int | None = None
    reranked_count: int | None = None
    final_sources: list[str] | None = None
    duration_ms: float | None = None


class StageEventModel(BaseModel):
    """A single recorded event within a pipeline stage."""

    stage: str
    started_at: str  # ISO 8601 string — already serialised by serialize_value()
    ended_at: str
    duration_ms: float
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    error: str | None = None


class ExecutionTraceModel(BaseModel):
    """Complete execution trace for a single question→answer run."""

    trace_id: str
    started_at: str
    ended_at: str
    duration_ms: float
    planner_events: list[StageEventModel]
    worker_events: list[StageEventModel]
    reviewer_events: list[StageEventModel]
    retrieval_trace: RetrievalTraceModel
    final_answer: str


# ---------------------------------------------------------------------------
# Top-level response models
# ---------------------------------------------------------------------------

class AskResponse(BaseModel):
    """Response model for the /ask endpoint."""

    trace_id: str = Field(description="Unique ID for this execution.")
    user_input: str
    plan: str
    selected_tool: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    draft_answer: str | None = None
    final_answer: str
    review_feedback: str
    retrieved_sources: list[str] | None = None
    execution_trace: ExecutionTraceModel | None = None


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""

    status: str = Field(description="'ok' when the service is healthy.")
    runtime_initialized: bool = Field(
        description="True when AssistantRuntime.setup() has completed."
    )
