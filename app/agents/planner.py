import structlog
from datetime import datetime
from typing import Optional
from app.contracts.tools import ToolDecision
from app.contracts.agent import AgentState
from app.utils.llm import get_llm, extract_usage
from app.tools.registry import TOOLS
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)

def planner_node(state: AgentState) -> AgentState:
    """Evaluate question using structured LLM output for tool selection"""
    logger.info(
        "node_started",
        node="planner_node",
        input=state.user_input
    )

    started = datetime.now()

    # Use LLM with structured output to decide which tool to use
    tool_decision, token_usage = get_tool_decision(state.user_input)

    logger.info(
        "tool_decision_made",
        selected_tool=tool_decision.tool,
        reason=tool_decision.reason
    )

    state.plan = tool_decision.reason
    state.selected_tool = tool_decision.tool
    state.tool_input = tool_decision.tool_input

    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings["planner"] = {
        "started_at": started,
        "ended_at": datetime.now()
    }

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage["planner"] = {
        "llm_calls": 1,
        "token_usage": token_usage,
    }

    return state

def get_tool_decision(question: str) -> tuple[ToolDecision, Optional[dict]]:
    """Use LLM with structured output to decide which tool to use.

    Returns (decision, token_usage): token_usage is the
    {"input_tokens", "output_tokens", "model"} shape from
    app.utils.llm.extract_usage, or None if the provider gave no usage
    metadata. include_raw=True is required to reach usage_metadata at
    all - the parsed Pydantic model alone carries no token information.
    """

    # Build tool descriptions for the prompt from TOOLS registry
    tool_options = "\n".join([
        f"- {tool}: {metadata['description']}" 
        for tool, metadata in TOOLS.items()
    ])

    # Build the prompt for tool selection
    tool_selection_prompt = format_prompt(
        "planner.txt",
        question=question,
        tool_options=tool_options
    )

    logger.info(
        "get_tool_decision",
        question=question,
        prompt_length=len(tool_selection_prompt)
    )

    # Use structured output with Pydantic model, include_raw=True to reach
    # usage_metadata (only present on the raw AIMessage, not the parsed model)
    llm = get_llm()
    llm_with_structure = llm.with_structured_output(ToolDecision, include_raw=True)
    outcome = llm_with_structure.invoke(tool_selection_prompt)
    response = outcome["parsed"]
    token_usage = extract_usage(outcome["raw"], model_name=llm.model_name)

    logger.debug(
        "get_tool_decision_response",
        tool=response.tool,
        reason=response.reason
    )

    return response, token_usage
