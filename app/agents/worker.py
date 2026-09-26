from datetime import datetime
import structlog
from app.tools.registry import TOOLS
from app.contracts.agent import AgentState

# Get logger for this module
logger = structlog.get_logger(__name__)

def worker_node(state: AgentState) -> AgentState:
    """Worker node that invokes the Tool selected by the Planner.

    Dispatch is tool-agnostic: each registry entry's "invoke" adapter
    knows its own input model, tool_input key, and result shape, so this
    function does not need per-tool knowledge (see app.tools.registry).
    """
    logger.info(
        "node_started",
        node="worker_node",
        selected_tool=state.selected_tool,
        tool_input=state.tool_input
    )

    started = datetime.now()

    tool_input = state.tool_input or {}  # Safely handle None
    tool_result = None
    retrieved_sources = None
    retrieval_trace = None

    tool_entry = TOOLS.get(state.selected_tool)

    if tool_entry is None:
        logger.error(
            "unknown_tool_selected",
            selected_tool=state.selected_tool
        )
        tool_result = f"Error: Unknown tool '{state.selected_tool}' was selected"
    else:
        try:
            outcome = tool_entry["invoke"](tool_input, state.user_input)
            tool_result = outcome["result"]
            retrieved_sources = outcome["sources"]
            retrieval_trace = outcome["retrieval_trace"]
        except Exception as e:
            logger.error(
                "tool_execution_failed",
                selected_tool=state.selected_tool,
                error=str(e)
            )
            tool_result = f"Error executing {state.selected_tool}: {str(e)}"

    state.tool_output = str(tool_result)
    state.draft_answer = f"Tool result:\n{state.tool_output}"
    state.retrieved_sources = retrieved_sources
    state.retrieval_trace = retrieval_trace
    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings["worker"] = {
        "started_at": started,
        "ended_at": datetime.now()
    }

    logger.debug(
        "tool_execution_completed",
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0
    )

    return state
