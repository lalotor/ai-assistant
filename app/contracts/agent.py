from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

from app.contracts.trace import RetrievalTrace


ReviewDecision = Literal["approve", "revise", "abstain"]
ReviewOutcome = Literal[
    "approved",
    "revised",
    "abstained",
    "budget_exhausted",
    "revision_skipped",
]


class AgentState(BaseModel):
    """Model representing the state of the agent during a conversation."""
    user_input: str

    plan: Optional[str] = None

    selected_tool: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None

    draft_answer: Optional[str] = None
    initial_draft_answer: Optional[str] = None
    final_answer: Optional[str] = None

    review_feedback: Optional[str] = None
    initial_review_decision: Optional[ReviewDecision] = None
    initial_review_feedback: Optional[str] = None
    review_decision: Optional[ReviewDecision] = None
    revision_feedback: Optional[str] = None
    revision_count: int = 0
    revision_enabled: bool = False
    review_outcome: Optional[ReviewOutcome] = None

    retrieved_sources: Optional[list[str]] = None

    stage_timings: Optional[Dict[str, Any]] = None
    stage_llm_usage: Optional[Dict[str, Any]] = None
    trace_id: str
    retrieval_trace: Optional[RetrievalTrace] = None


class ReviewResult(BaseModel):
    """Structured output model for LLM review results."""

    decision: ReviewDecision = Field(
        description=(
            "The review decision: 'approve' when the draft is acceptable, "
            "'revise' when a specific material deficiency can be corrected from "
            "the existing tool output/evidence, or 'abstain' when the answer "
            "cannot be responsibly produced."
        )
    )
    final_answer: str = Field(description="The final answer to the user's question")
    feedback: str = Field(
        description=(
            "The review explanation. For 'revise', the specific, actionable "
            "correction the revision step must make."
        )
    )
    evidence_sufficient: bool = Field(
        description=(
            "Whether the provided tool output contains enough direct evidence "
            "to support the answer to the user's question"
        )
    )
