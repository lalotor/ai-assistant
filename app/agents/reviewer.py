import structlog
from app.agents.model import ReviewResult
from app.utils.llm import get_llm
from app.agents.state import AgentState

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

    review_prompt = f"""
    You are an expert AI assistant that helps reviews and improves AI generated content.
    
    User Question:
    {state.user_input}
    
    Draft answer based on the tool output:
    {state.draft_answer}

    Selected tool:
    {state.selected_tool}
    
    Based on the user question and the draft answer, decide if the draft answer is sufficient or if it needs improvement. If it needs improvement, 
    provide an improved final answer and a short feedback; if not, just return the draft answer as the final answer with feedback that it's good.

    If the selected tool is "none" or not identified, that means that the question was not technical, so simply respond in the final_answer with 
    "No technical question or no tool selected, try again" and no feedback.
    """

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

    return state
