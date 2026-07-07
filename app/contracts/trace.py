import dataclasses
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class StageEvent:
    """A single event recorded during a pipeline stage."""
    stage: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    error: Optional[str] = None

@dataclass
class RetrievalTrace:
    """Traces the retrieval pipeline: vector search → keyword search → reranking."""
    query: str
    vector_results_count: Optional[int] = None
    keyword_results_count: Optional[int] = None
    merged_count: Optional[int] = None
    reranked_count: Optional[int] = None
    final_sources: Optional[list[str]] = None
    duration_ms: Optional[float] = None

@dataclass
class ExecutionTrace:
    """Complete trace of a single question→answer execution."""
    trace_id: str
    started_at: datetime
    ended_at: datetime

    planner_events: list[StageEvent]
    worker_events: list[StageEvent]
    reviewer_events: list[StageEvent]

    retrieval_trace: RetrievalTrace

    final_answer: str

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary with datetime fields as ISO 8601 strings."""
        raw = dataclasses.asdict(self)
        return _serialize_value(raw)

def _serialize_value(value: Any) -> Any:
    """Recursively convert datetime objects to ISO 8601 strings for JSON serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value
