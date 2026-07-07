import structlog
from datetime import datetime
from app.contracts.tools import ToolDecision
from app.contracts.agent import AgentState
from app.utils.llm import get_llm
from app.tools.registry import TOOLS
from app.prompts import format_prompt

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def planner_node(state: AgentState) -> AgentState:
    """Evaluate question using structured LLM output for tool selection"""
    logger.info(
        "node_started",
        node="planner_node",
        input=state.user_input
    )

    started = datetime.now()

    # Use LLM with structured output to decide which tool to use
    tool_decision = get_tool_decision(state.user_input)

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

    return state

def get_tool_decision(question: str) -> ToolDecision:
    """Use LLM with structured output to decide which tool to use."""

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

    # Use structured output with Pydantic model
    llm_with_structure = llm.with_structured_output(ToolDecision)
    response = llm_with_structure.invoke(tool_selection_prompt)

    logger.debug(
        "get_tool_decision_response",
        tool=response.tool,
        reason=response.reason
    )

    return response
