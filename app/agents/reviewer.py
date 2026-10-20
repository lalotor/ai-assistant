from datetime import datetime
import structlog
from app.utils.llm import get_llm, extract_usage
from app.contracts.agent import AgentState, ReviewResult
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)

def reviewer_node(state: AgentState) -> AgentState:
    """Reviewer node that reviews the draft answer and provides feedback or improvements."""
    logger.info(
        "node_started",
        node="reviewer_node",
        input=state.user_input,
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0
    )

    started = datetime.now()

    if state.selected_tool == "doc_retriever" and not state.retrieved_sources:
        state.final_answer = "I couldn't find relevant documentation to support an answer to this question."
        state.review_feedback = "No retrieved sources were available; abstained to avoid an unsupported answer."

        if state.stage_timings is None:
            state.stage_timings = {}
        state.stage_timings["reviewer"] = {
            "started_at": started,
            "ended_at": datetime.now()
        }

        if state.stage_llm_usage is None:
            state.stage_llm_usage = {}
        state.stage_llm_usage["reviewer"] = {
            "llm_calls": 0,
            "token_usage": None,
        }

        logger.info("reviewer_abstained", reason="no_retrieved_sources")
        return state

    review_prompt = format_prompt(
        "reviewer.txt",
        user_input=state.user_input,
        draft_answer=state.draft_answer,
        selected_tool=state.selected_tool
    )

    # Use structured output with Pydantic model, include_raw=True to reach
    # usage_metadata (only present on the raw AIMessage, not the parsed model)
    llm = get_llm()
    llm_with_structure = llm.with_structured_output(ReviewResult, include_raw=True)
    outcome = llm_with_structure.invoke(review_prompt)
    response = outcome["parsed"]
    token_usage = extract_usage(outcome["raw"], model_name=llm.model_name)

    logger.debug(
        "review_complete",
        final_answer_length=len(response.final_answer),
        feedback=response.feedback
    )

    if state.selected_tool == "doc_retriever" and not response.evidence_sufficient:
        state.final_answer = (
            "The available documentation does not provide enough evidence to answer this question reliably."
        )
        state.review_feedback = (
            "The retrieved sources did not sufficiently support an answer; "
            "abstained to avoid unsupported claims."
        )
        logger.info("reviewer_abstained", reason="insufficient_evidence")
    else:
        state.final_answer = response.final_answer
        state.review_feedback = response.feedback

    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings["reviewer"] = {
        "started_at": started,
        "ended_at": datetime.now()
    }

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage["reviewer"] = {
        "llm_calls": 1,
        "token_usage": token_usage,
    }

    return state
