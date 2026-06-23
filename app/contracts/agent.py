from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class AgentState(BaseModel):
    """Model representing the state of the agent during a conversation."""
    user_input: str

    plan: Optional[str] = None

    selected_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None

    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None

    review_feedback: Optional[str] = None

    retrieved_sources: Optional[list[str]] = None

class ReviewResult(BaseModel):
    """Structured output model for LLM review results."""

    final_answer: str = Field(description="The final answer to the user's question")
    feedback: str = Field(description="Feedback about the draft answer")
