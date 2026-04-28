import structlog
from dotenv import load_dotenv
from app.utils.llm import get_llm
from app.tools.registry import TOOLS
from app.agents.state import AgentState
from app.tools.code_explainer import CodeInput
from app.tools.doc_retriever import DocInput
from app.tools.architecture_advisor import ArchInput

# Load variables from .env file
load_dotenv()

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def worker_node(state: AgentState) -> AgentState:
    """Worker node that decides which tool to call based on user input and LLM decision."""
    logger.info(
        "node_started",
        node="worker_node",
        selected_tool=state.selected_tool,
        tool_input=state.tool_input
    )

    # Route to the appropriate tool based on selection
    tool_result = None
    tool_input = state.tool_input or {}  # Safely handle None

    try:
        if state.selected_tool == "code_explainer":
            code = tool_input.get("code") or state.user_input
            result = TOOLS["code_explainer"]["function"](CodeInput(code=code))
            tool_result = result.explanation
        elif state.selected_tool == "doc_retriever":
            query = tool_input.get("query") or state.user_input
            result = TOOLS["doc_retriever"]["function"](DocInput(query=query))
            tool_result = result.context
        elif state.selected_tool == "architecture_advisor":
            question = tool_input.get("question") or state.user_input
            result = TOOLS["architecture_advisor"]["function"](ArchInput(question=question))
            tool_result = result.advice
        else:
            logger.error(
                "unknown_tool_selected",
                selected_tool=state.selected_tool
            )
            tool_result = f"Error: Unknown tool '{state.selected_tool}' was selected"

    except Exception as e:
        logger.error(
            "tool_execution_failed",
            selected_tool=state.selected_tool,
            error=str(e)
        )
        tool_result = f"Error executing {state.selected_tool}: {str(e)}"

    state.tool_output = str(tool_result)
    state.draft_answer = f"Tool result:\n{state.tool_output}"

    logger.info(
        "tool_execution_completed",
        draft_answer_length=len(state.draft_answer) if state.draft_answer else 0
    )

    return state
