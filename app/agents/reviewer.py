from datetime import datetime
from typing import Optional

import structlog

from app.utils.llm import get_llm, extract_usage
from app.contracts.agent import AgentState, ReviewResult
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)


_ABSTENTION_NO_SOURCES = (
    "I couldn't find relevant documentation to support an answer to this question."
)
_ABSTENTION_INSUFFICIENT_EVIDENCE = (
    "The available documentation does not provide enough evidence to answer this question reliably."
)
_ABSTENTION_GENERIC = "I couldn't produce a reliable answer to this question."
_BUDGET_EXHAUSTED_LIMITATION = (
    "Note: this answer was revised once, but the reviewer still identified a material "
    "deficiency within the available evidence. Treat it as provisional."
)
_NO_SOURCES_FEEDBACK = (
    "No retrieved sources were available; abstained to avoid an unsupported answer."
)
_INSUFFICIENT_EVIDENCE_FEEDBACK = (
    "The retrieved sources did not sufficiently support an answer; "
    "abstained to avoid unsupported claims."
)


def reviewer_node(state: AgentState) -> AgentState:
    """Review the draft answer and return an explicit review decision.

    The reviewer runs once before revision and, when a revision is allowed,
    once more on the revised draft. The second pass cannot request another
    revision: the graph's revision budget is enforced in routing as well as
    in this node.
    """
    stage = _review_stage(state)
    revision_allowed = (
        state.revision_enabled
        and state.revision_count == 0
        and state.selected_tool not in (None, "none")
    )

    logger.info(
        "node_started",
        node="reviewer_node",
        review_stage=stage,
        revision_allowed=revision_allowed,
        input_length=len(state.user_input),
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0,
    )

    started = datetime.now()

    if state.selected_tool == "doc_retriever" and not state.retrieved_sources:
        _set_abstention(
            state,
            answer=_ABSTENTION_NO_SOURCES,
            feedback=_NO_SOURCES_FEEDBACK,
            stage=stage,
            started=started,
        )
        logger.info(
            "reviewer_abstained",
            reason="no_retrieved_sources",
            review_stage=stage,
        )
        return state

    review_prompt = format_prompt(
        "reviewer.txt",
        user_input=state.user_input,
        draft_answer=state.draft_answer or "",
        selected_tool=state.selected_tool or "none",
        revision_policy=_revision_policy(revision_allowed),
    )

    # Use structured output with Pydantic model, include_raw=True to reach
    # usage_metadata (only present on the raw AIMessage, not the parsed model)
    llm = get_llm()
    llm_with_structure = llm.with_structured_output(ReviewResult, include_raw=True)
    outcome = llm_with_structure.invoke(review_prompt)
    response = outcome["parsed"]
    token_usage = extract_usage(outcome["raw"], model_name=llm.model_name)

    decision = response.decision
    feedback = (response.feedback or "").strip()
    has_actionable_feedback = bool(feedback)

    logger.debug(
        "review_complete",
        review_stage=stage,
        decision=decision,
        final_answer_length=len(response.final_answer or ""),
        feedback_length=len(feedback),
    )

    # Route-specific evidence gate: source presence alone is not proof, and a
    # revision must never be used to invent evidence that was not retrieved.
    if state.selected_tool == "doc_retriever" and not response.evidence_sufficient:
        _set_abstention(
            state,
            answer=_ABSTENTION_INSUFFICIENT_EVIDENCE,
            feedback=_INSUFFICIENT_EVIDENCE_FEEDBACK,
            stage=stage,
            started=started,
            token_usage=token_usage,
            llm_calls=1,
        )
        logger.info(
            "reviewer_abstained",
            reason="insufficient_evidence",
            review_stage=stage,
        )
        return state

    if decision == "abstain":
        _set_abstention(
            state,
            answer=_ABSTENTION_GENERIC,
            feedback=feedback or "The reviewer could not produce a reliable answer.",
            stage=stage,
            started=started,
            token_usage=token_usage,
            llm_calls=1,
        )
        logger.info(
            "reviewer_abstained",
            reason="reviewer_decision",
            review_stage=stage,
        )
        return state

    if state.revision_count == 0:
        state.initial_review_decision = decision
        state.initial_review_feedback = feedback

    state.review_decision = decision
    state.review_feedback = feedback

    if decision == "revise" and revision_allowed and has_actionable_feedback:
        state.revision_feedback = feedback
        state.review_outcome = None
        _record_stage(state, stage, started, llm_calls=1, token_usage=token_usage)
        logger.info(
            "reviewer_requested_revision",
            review_stage=stage,
            feedback_length=len(feedback),
        )
        return state

    state.final_answer = response.final_answer or state.draft_answer

    if decision == "revise":
        if state.revision_count > 0:
            state.review_outcome = "budget_exhausted"
            state.final_answer = _with_budget_limitation(state.final_answer)
            logger.info(
                "reviewer_budget_exhausted",
                review_stage=stage,
            )
        else:
            state.review_outcome = "revision_skipped"
            logger.info(
                "reviewer_revision_skipped",
                reason=(
                    "revision_disabled"
                    if not state.revision_enabled
                    else "no_actionable_feedback"
                ),
                review_stage=stage,
            )
    else:
        state.review_outcome = "revised" if state.revision_count > 0 else "approved"

    _record_stage(state, stage, started, llm_calls=1, token_usage=token_usage)
    return state


def _review_stage(state: AgentState) -> str:
    """The timing/usage key for this reviewer pass."""
    return "reviewer" if state.revision_count == 0 else "reviewer_final"


def _revision_policy(revision_allowed: bool) -> str:
    if revision_allowed:
        return (
            "A single revision is available. Choose 'revise' only when the draft has "
            "a specific, material deficiency that can be corrected using the existing "
            "tool output/evidence. Put the exact correction in feedback."
        )
    return (
        "No revision attempt is available. Choose 'approve' or 'abstain' only. "
        "Do not choose 'revise'."
    )


def _set_abstention(
    state: AgentState,
    *,
    answer: str,
    feedback: str,
    stage: str,
    started: datetime,
    token_usage: Optional[dict] = None,
    llm_calls: int = 0,
) -> None:
    state.final_answer = answer
    state.review_feedback = feedback
    state.review_decision = "abstain"
    state.review_outcome = "abstained"

    if state.revision_count == 0:
        state.initial_review_decision = "abstain"
        state.initial_review_feedback = feedback

    _record_stage(state, stage, started, llm_calls=llm_calls, token_usage=token_usage)


def _record_stage(
    state: AgentState,
    stage: str,
    started: datetime,
    *,
    llm_calls: int,
    token_usage: Optional[dict],
) -> None:
    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings[stage] = {
        "started_at": started,
        "ended_at": datetime.now(),
    }

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage[stage] = {
        "llm_calls": llm_calls,
        "token_usage": token_usage,
    }


def _with_budget_limitation(answer: Optional[str]) -> str:
    base = (answer or "").strip()
    if not base:
        base = "The revised answer could not be fully approved."
    if _BUDGET_EXHAUSTED_LIMITATION in base:
        return base
    return f"{base}\n\n{_BUDGET_EXHAUSTED_LIMITATION}"
