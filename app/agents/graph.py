from typing import Literal
import structlog
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from app.agents.state import AssistantState
from app.utils.llm import get_llm
from app.tools.code_explainer import code_explainer

# Load variables from .env file
load_dotenv()

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm(model="gpt-5-nano")

def evaluate_question(state: AssistantState) -> Command[Literal["tool_call", "final_answer"]]:
    """Evaluate question"""
    logger.info(
        "node_started",
        node="evaluate_question",
        input=state.get('input'),
        tool_result=state.get('tool_result')
    ) 

    goto = "final_answer"
    decision = "direct_answer"
    output = None
    if not state.get('output') and not state.get('tool_result'):
        includes_code = validate_code_prompt(state.get('input')) == "YES"
        if includes_code:
            goto = "tool_call"
            decision = "call_tool"
        else:
            output = f"Direct answer to your question: {get_direct_answer(state.get('input'))}"

    logger.info(
        "node_completed",
        node="evaluate_question",
        decision=decision,
        goto=goto
    )

    return Command(
        update={
            "decision": decision,
            "output": output,
            "messages": [HumanMessage(content=f"Processing question: {state['input']}")]
        },
        goto=goto
    )

def tool_call(state: AssistantState) -> Command[Literal["evaluate_question"]]:
    """Call tool"""
    logger.info(
        "node_started",
        node="tool_call",
        input=state.get('input')
    )

    tool_result = code_explainer(code_snippet=state.get('input'), llm=llm)

    return Command(
        update={"tool_result": tool_result},
        goto="evaluate_question"
    )

def final_answer(state: AssistantState) -> dict:
    """Final answer for the question"""
    logger.info(
        "node_started",
        node="final_answer",
        output=state.get('output')
    )

    output = state.get('output')
    if state.get('tool_result'):
        output = f"Since your question includes code, here is the explanation: {state.get('tool_result')}"

    return {
        "output": output
    }

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

    """ # Add retry policy for nodes that might have transient failures
    workflow.add_node(
        "search_documentation",
        search_documentation,
        retry_policy=RetryPolicy(max_attempts=3)
    )
    logger.info(
        "retry_policy_configured",
        node="search_documentation",
        max_attempts=3
    ) """

    # Add only the essential edges
    logger.info("adding_workflow_edges")
    workflow.add_edge(START, "evaluate_question")
    workflow.add_edge("final_answer", END)

    # Compile with checkpointer for persistence, in case run graph with Local_Server --> Please compile without checkpointer
    logger.info("compiling_graph_with_checkpointer")
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    logger.info(
        "graph_construction_completed",
        nodes_count=3,
        has_checkpointer=True
    )

    return app

def validate_code_prompt(input: str) -> str:
    """"Validate if question includes code snippet or not"""
    # Build the prompt with formatted context
    includes_code_prompt = f"""
    Validate if question includes code snippet or not:
    {input}

    Guidelines:
    - You are an expert AI Assistant
    - Response only with "YES" or "NO"
    """

    logger.info(
        "validate_code_prompt",
        question=input,
        prompt_length=len(includes_code_prompt)
    )

    response = llm.invoke(includes_code_prompt)

    logger.info(
        "validate_code_prompt",
        response=response
    )

    return response.content

def get_direct_answer(input: str) -> str:
    """Get direct answer for the question without calling tool"""
    # Build the prompt with formatted context
    direct_answer_prompt = f"""
    Provide a direct answer to the question:
    {input}

    Guidelines:
    - You are an expert AI Technical Assistant
    - Response only technical question, for any other case respond: "This question is not technical, please try again"
    - User MarkDown as the formatting language for the answer, and include code snippets if necessary
    """

    logger.info(
        "get_direct_answer",
        question=input,
        prompt_length=len(direct_answer_prompt)
    )

    response = llm.invoke(direct_answer_prompt)

    logger.info(
        "get_direct_answer",
        response=response
    )

    return response.content
