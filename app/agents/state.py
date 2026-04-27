from typing import Any, Dict, Optional, TypedDict, Literal
from pydantic import BaseModel

class AssistantState(TypedDict):
    input: str
    decision: Literal["direct_answer", "call_tool"]
    selected_tool: str | None  # The tool selected by LLM (code_explainer, doc_retriever, architecture_advisor, none)
    tool_reason: str | None  # Reason for tool selection
    tool_result: str | None
    output: str | None

class AgentState(BaseModel):
    user_input: str

    plan: Optional[str] = None

    selected_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None

    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None

    review_feedback: Optional[str] = None
