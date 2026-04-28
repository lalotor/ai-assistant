from typing import Any, Dict, Optional, TypedDict, Literal
from pydantic import BaseModel

class AgentState(BaseModel):
    user_input: str

    plan: Optional[str] = None

    selected_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None

    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None

    review_feedback: Optional[str] = None
