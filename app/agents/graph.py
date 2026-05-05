import structlog
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.planner import planner_node
from app.agents.worker import worker_node
from app.agents.reviewer import reviewer_node
from app.utils.llm import get_llm

# Load variables from .env file
load_dotenv()

# Get logger for this module
logger = structlog.get_logger(__name__)

llm = get_llm()

def get_graph():
    """Construct and compile the graph workflow."""
    logger.info("graph_construction_started")

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes with appropriate error handling
    logger.info("adding_workflow_nodes")
    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("reviewer", reviewer_node)

    # Add only the essential edges
    logger.info("adding_workflow_edges")
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "worker")
    workflow.add_edge("worker", "reviewer")
    workflow.add_edge("reviewer", END)

    # Compile graph
    logger.info("compiling_graph")
    app = workflow.compile()

    logger.info(
        "graph_construction_completed",
        nodes_count=3,
        has_checkpointer=False
    )

    return app
