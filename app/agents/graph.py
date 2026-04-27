from typing import Literal
import structlog
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from app.agents.state import AgentState, AssistantState
from app.agents.tool_decision import ToolDecision
from app.agents.planner import planner_node
from app.utils.llm import get_llm
from app.tools.code_explainer import CodeInput
from app.tools.doc_retriever import DocInput
from app.tools.architecture_advisor import ArchInput
from app.tools.registry import TOOLS

# Load variables from .env file
load_dotenv()

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def tool_call(state: AssistantState) -> Command[Literal["evaluate_question"]]:
    """Call the selected tool based on LLM decision"""
    selected_tool = state.get('selected_tool')
    user_input = state.get('input')
    
    logger.info(
        "node_started",
        node="tool_call",
        selected_tool=selected_tool,
        input=user_input
    )

    # Route to the appropriate tool based on selection
    tool_result = None
    
    if selected_tool == "code_explainer":
        result = TOOLS["code_explainer"]["function"](CodeInput(code=user_input))
        tool_result = result.explanation
    
    elif selected_tool == "doc_retriever":
        result = TOOLS["doc_retriever"]["function"](DocInput(query=user_input))
        tool_result = result.context
    
    elif selected_tool == "architecture_advisor":
        result = TOOLS["architecture_advisor"]["function"](ArchInput(question=user_input))
        tool_result = result.advice
    
    else:
        logger.error(
            "unknown_tool_selected",
            selected_tool=selected_tool
        )
        tool_result = f"Error: Unknown tool '{selected_tool}' was selected"

    logger.info(
        "tool_execution_completed",
        selected_tool=selected_tool,
        result_length=len(tool_result) if tool_result else 0
    )

    return Command(
        update={"tool_result": tool_result},
        goto="evaluate_question"
    )

def final_answer(state: AssistantState) -> dict:
    """Final answer for the question"""
    logger.info(
        "node_started",
        node="final_answer",
        selected_tool=state.get('selected_tool'),
        tool_reason=state.get('tool_reason'),
        tool_result=state.get('tool_result')
    )

    if state.get('tool_result'):
        selected_tool = state.get('selected_tool', 'unknown')
        tool_reason = state.get('tool_reason', 'No reason provided')
        output = f"""**Tool Used:** {selected_tool}
**Reason:** {tool_reason}

**Result:**
{state.get('tool_result')}"""
    else:
        output = f"Direct answer to your question: {get_direct_answer(state.get('input'))}"

    return {
        "output": output
    }

def get_direct_answer(question: str) -> str:
    """Get direct answer for the question without calling tool"""
    # Build the prompt with formatted context
    direct_answer_prompt = f"""
    Provide a direct answer to the question:
    {question}

    Guidelines:
    - You are an expert AI Technical Assistant
    - Response only technical question, for any other case respond: "This question is not technical, please try again"
    - User MarkDown as the formatting language for the answer, and include code snippets if necessary
    """

    logger.info(
        "get_direct_answer",
        question=question,
        prompt_length=len(direct_answer_prompt)
    )

    response = llm.invoke(direct_answer_prompt)

    logger.info(
        "get_direct_answer",
        response=response
    )

    return response.content

def get_graph():
    """Construct and compile the graph workflow."""
    logger.info("graph_construction_started")

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes with appropriate error handling
    logger.info("adding_workflow_nodes")
    workflow.add_node("planner", planner_node)

    # Add only the essential edges
    logger.info("adding_workflow_edges")
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", END)

    # Compile graph
    logger.info("compiling_graph")
    app = workflow.compile()

    logger.info(
        "graph_construction_completed",
        nodes_count=1,
        has_checkpointer=True
    )

    return app
