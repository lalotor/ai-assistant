from datetime import datetime
import structlog
from app.tools.registry import TOOLS
from app.contracts.agent import AgentState
from app.contracts.retrieval import RetrievalUnavailableError
from app.contracts.tools import InvalidToolSelectionError, ToolExecutionError

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
    # Unknown-tool and exception paths make zero LLM calls: nothing ran.
    llm_calls = 0
    token_usage = None

    tool_entry = TOOLS.get(state.selected_tool)

    if tool_entry is None:
        logger.error(
            "unknown_tool_selected",
            selected_tool=state.selected_tool,
            failure_category="invalid_tool_selection",
        )
        raise InvalidToolSelectionError(
            f"Unknown tool '{state.selected_tool}' was selected."
        )
    else:
        try:
            outcome = tool_entry["invoke"](tool_input, state.user_input)
            tool_result = outcome["result"]
            retrieved_sources = outcome["sources"]
            retrieval_trace = outcome["retrieval_trace"]
            # .get() with defaults: tolerates older/mocked invoke outcomes
            # that predate Week 9's llm_calls/token_usage keys.
            llm_calls = outcome.get("llm_calls", 0)
            token_usage = outcome.get("token_usage")
        except RetrievalUnavailableError:
            logger.error(
                "tool_execution_failed",
                selected_tool=state.selected_tool,
                failure_category="retrieval_unavailable",
            )
            raise
        except Exception as e:
            logger.error(
                "tool_execution_failed",
                selected_tool=state.selected_tool,
                failure_category="tool_execution_error",
                error_type=type(e).__name__,
            )
            raise ToolExecutionError("Tool execution failed.") from e

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

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage["worker"] = {
        "llm_calls": llm_calls,
        "token_usage": token_usage,
    }

    logger.debug(
        "tool_execution_completed",
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0
    )

    return state
