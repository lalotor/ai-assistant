from datetime import datetime
from typing import Any, Optional
from dataclasses import asdict, dataclass, fields

from app.utils.util import serialize_value

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

    @classmethod
    def from_dict(cls, data: dict) -> "StageEvent":
        """Create a StageEvent instance from a dictionary, ignoring any extra fields."""
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

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

    @classmethod
    def from_dict(cls, data: dict) -> "RetrievalTrace":
        """Create a RetrievalTrace instance from a dictionary, ignoring any extra fields."""
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

@dataclass
class ExecutionTrace:
    """Complete trace of a single question→answer execution."""
    trace_id: str
    started_at: datetime
    ended_at: datetime
    duration_ms: float

    planner_events: list[StageEvent]
    worker_events: list[StageEvent]
    reviewer_events: list[StageEvent]

    retrieval_trace: RetrievalTrace

    final_answer: str

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary with datetime fields as ISO 8601 strings."""
        raw = asdict(self)
        return serialize_value(raw)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionTrace":
        """Create an ExecutionTrace instance from a dictionary, ignoring any extra fields."""
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        if 'retrieval_trace' in filtered_data and filtered_data['retrieval_trace']:
            filtered_data['retrieval_trace'] = RetrievalTrace.from_dict(filtered_data['retrieval_trace'])
        if 'planner_events' in filtered_data:
            filtered_data['planner_events'] = [StageEvent.from_dict(e) for e in filtered_data['planner_events']]
        if 'worker_events' in filtered_data:
            filtered_data['worker_events'] = [StageEvent.from_dict(e) for e in filtered_data['worker_events']]
        if 'reviewer_events' in filtered_data:
            filtered_data['reviewer_events'] = [StageEvent.from_dict(e) for e in filtered_data['reviewer_events']]

        return cls(**filtered_data)
