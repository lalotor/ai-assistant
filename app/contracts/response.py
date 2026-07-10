from typing import Any, Dict, Optional
from dataclasses import asdict, dataclass, fields

from app.contracts.trace import ExecutionTrace
from app.utils.util import serialize_value

@dataclass
class QueryResponse:
    """Structured output model for LLM query responses."""
    user_input: str
    plan: str
    selected_tool: str
    tool_input: Dict[str, Any]
    tool_output: str
    draft_answer: str
    final_answer: str
    review_feedback: str
    retrieved_sources: Optional[list[str]] = None
    execution_trace: Optional[ExecutionTrace] = None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary with datetime fields as ISO 8601 strings."""
        raw = asdict(self)
        return serialize_value(raw)

    @classmethod
    def from_dict(cls, data: dict) -> "QueryResponse":
        """Create a QueryResponse instance from a dictionary, ignoring any extra fields."""
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        if 'execution_trace' in filtered_data and filtered_data['execution_trace']:
            filtered_data['execution_trace'] = ExecutionTrace.from_dict(filtered_data['execution_trace'])

        return cls(**filtered_data)
