from datetime import datetime

import structlog

from app.contracts.agent import AgentState
from app.prompts import format_prompt
from app.utils.llm import get_llm, extract_usage

# Get logger for this module
logger = structlog.get_logger(__name__)


def revision_node(state: AgentState) -> AgentState:
    """Rewrite the current draft using the reviewer's actionable feedback.

    The revision is grounded in the tool output already collected by the
    Worker; it never re-runs the tool or re-retrieves documents, so the
    source provenance on the state is preserved.
    """
    logger.info(
        "node_started",
        node="revision_node",
        selected_tool=state.selected_tool,
        revision_count=state.revision_count,
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0,
        feedback_length=len(state.revision_feedback or ""),
    )

    started = datetime.now()

    sources = ", ".join(state.retrieved_sources or []) or "none"
    revision_prompt = format_prompt(
        "revision.txt",
        user_input=state.user_input,
        draft_answer=state.draft_answer or "",
        review_feedback=state.revision_feedback or state.review_feedback or "",
        tool_output=state.tool_output or "",
        retrieved_sources=sources,
        selected_tool=state.selected_tool or "none",
    )

    llm = get_llm()
    response = llm.invoke(revision_prompt)
    revised_answer = str(response.content or "").strip()

    if not revised_answer:
        raise ValueError("Revision produced an empty answer.")

    token_usage = extract_usage(response, model_name=llm.model_name)

    if state.initial_draft_answer is None:
        state.initial_draft_answer = state.draft_answer
    state.draft_answer = revised_answer
    state.revision_count += 1
    state.review_decision = None

    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings["revision"] = {
        "started_at": started,
        "ended_at": datetime.now(),
    }

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage["revision"] = {
        "llm_calls": 1,
        "token_usage": token_usage,
    }

    logger.info(
        "revision_completed",
        revision_count=state.revision_count,
        revised_answer_length=len(revised_answer),
    )

    return state
