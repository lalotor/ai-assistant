from typing import Literal
import structlog
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from app.agents.state import AssistantState
from app.utils.llm import get_llm
from app.tools.code_explainer import code_explainer, CodeInput

# Load variables from .env file
load_dotenv()

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def evaluate_question(state: AssistantState) -> Command[Literal["tool_call", "final_answer"]]:
    """Evaluate question"""
    logger.info(
        "node_started",
        node="evaluate_question",
        input=state.get('input'),
        tool_result=state.get('tool_result')
    )

    if not state.get('tool_result'):
        includes_code = validate_code_prompt(state.get('input')) == "YES"
        if includes_code:
            return Command(update={"decision": "call_tool"}, goto="tool_call")

    return Command(update={"decision": "direct_answer"}, goto="final_answer")

def tool_call(state: AssistantState) -> Command[Literal["evaluate_question"]]:
    """Call tool"""
    logger.info(
        "node_started",
        node="tool_call",
        input=state.get('input')
    )

    tool_result = code_explainer(CodeInput(code=state.get('input')))

    return Command(
        update={"tool_result": tool_result.explanation},
        goto="evaluate_question"
    )

def final_answer(state: AssistantState) -> dict:
    """Final answer for the question"""
    logger.info(
        "node_started",
        node="final_answer",
        tool_result=state.get('tool_result')
    )

    if state.get('tool_result'):
        output = f"Since your question includes code, here is the explanation: {state.get('tool_result')}"
    else:
        output = f"Direct answer to your question: {get_direct_answer(state.get('input'))}"

    return {
        "output": output
    }

def validate_code_prompt(question: str) -> str:
    """"Validate if question includes code snippet or not"""
    # Build the prompt with formatted context
    includes_code_prompt = f"""
    Validate if question includes code snippet or not:
    {question}

    Guidelines:
    - You are an expert AI Assistant
    - Response only with "YES" or "NO"
    """

    logger.info(
        "validate_code_prompt",
        question=question,
        prompt_length=len(includes_code_prompt)
    )

    response = llm.invoke(includes_code_prompt)

    logger.info(
        "validate_code_prompt",
        response=response
    )

    return response.content

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
    workflow = StateGraph(AssistantState)

    # Add nodes with appropriate error handling
    logger.info("adding_workflow_nodes")
    workflow.add_node("evaluate_question", evaluate_question)
    workflow.add_node("tool_call", tool_call)
    workflow.add_node("final_answer", final_answer)

    # Add only the essential edges
    logger.info("adding_workflow_edges")
    workflow.add_edge(START, "evaluate_question")
    workflow.add_edge("final_answer", END)

    # Compile graph
    logger.info("compiling_graph")
    app = workflow.compile()

    logger.info(
        "graph_construction_completed",
        nodes_count=3,
        has_checkpointer=True
    )

    return app
