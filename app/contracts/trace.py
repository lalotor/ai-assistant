from datetime import datetime
from typing import Any, Optional
from dataclasses import asdict, dataclass, fields

from app.utils.util import serialize_value

@dataclass
class StageEvent:
    """A single event recorded during a pipeline stage.

    llm_calls and token_usage are performance/cost metrics, not
    correctness data: llm_calls counts every LLM invocation made while
    running this stage (e.g. the Worker's llm_calls is 2, not 1, when
    the selected tool is doc_retriever and its reranking step actually
    runs an LLM call, since that's a second, otherwise-invisible LLM
    call. Week 9 Session 2b: doc_retriever's reranking step is skipped
    - 0 LLM calls, not 1 - when the merged candidate set is small enough
    that there's nothing meaningful to rerank; see
    app.tools.doc_retriever._TRIVIAL_RERANK_THRESHOLD). token_usage is
    {"input_tokens": int, "output_tokens": int, "model": str} summed
    across all of the stage's LLM calls, or None when no usage metadata
    was available (e.g. the provider didn't return it, or the stage made
    zero LLM calls).
    """
    stage: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_ms: Optional[float]
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any]
    error: Optional[str] = None
    llm_calls: int = 0
    token_usage: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "StageEvent":
        """Create a StageEvent instance from a dictionary, ignoring any extra fields."""
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

@dataclass
class RetrievalTrace:
    """Traces the retrieval pipeline: vector search → keyword search → merge → reranking.

    Week 9 Session 2a: vector_search_ms/keyword_search_ms/merge_ms/
    rerank_ms break duration_ms (the whole call's total) down by
    sub-stage, so a slow doc_retriever call can be attributed to a
    specific step instead of guessed at. Each defaults to None, not 0,
    when its stage was never measured (e.g. an older trace, or a stage
    that never ran) - 0 would falsely claim "this stage took no time"
    instead of "this stage's time is unknown".
    """
    query: str
    vector_results_count: Optional[int] = None
    keyword_results_count: Optional[int] = None
    merged_count: Optional[int] = None
    reranked_count: Optional[int] = None
    final_sources: Optional[list[str]] = None
    duration_ms: Optional[float] = None
    vector_search_ms: Optional[float] = None
    keyword_search_ms: Optional[float] = None
    merge_ms: Optional[float] = None
    rerank_ms: Optional[float] = None

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
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_ms: Optional[float]

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
