from datetime import datetime
import structlog
from app.utils.llm import get_llm
from app.contracts.agent import AgentState, ReviewResult
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def reviewer_node(state: AgentState) -> AgentState:
    """Reviewer node that reviews the draft answer and provides feedback or improvements."""
    logger.info(
        "node_started",
        node="reviewer_node",
        input=state.user_input,
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0
    )

    started = datetime.now()

    review_prompt = format_prompt(
        "reviewer.txt",
        user_input=state.user_input,
        draft_answer=state.draft_answer,
        selected_tool=state.selected_tool
    )

    # Use structured output with Pydantic model
    llm_with_structure = llm.with_structured_output(ReviewResult)
    response = llm_with_structure.invoke(review_prompt)

    logger.debug(
        "review_complete",
        final_answer_length=len(response.final_answer),
        feedback=response.feedback
    )

    state.final_answer = response.final_answer
    state.review_feedback = response.feedback

    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings["reviewer"] = {
        "started_at": started,
        "ended_at": datetime.now()
    }

    return state
