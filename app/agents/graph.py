import structlog
from datetime import datetime
from collections.abc import Callable
from langgraph.graph import StateGraph, START, END
import openai
from app.contracts.agent import AgentState
from app.contracts.errors import WorkflowStageError
from app.contracts.retrieval import RetrievalUnavailableError
from app.contracts.tools import InvalidToolSelectionError, ToolExecutionError
from app.agents.planner import planner_node
from app.agents.worker import worker_node
from app.agents.reviewer import reviewer_node
from app.agents.revision import revision_node

# Get logger for this module
logger = structlog.get_logger(__name__)


def _stage_node(stage: str, node: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
    def invoke(state: AgentState) -> AgentState:
        started = datetime.now()
        try:
            return node(state)
        except Exception as exc:
            stage_timings = dict(state.stage_timings or {})
            stage_timings[stage] = {
                "started_at": started,
                "ended_at": datetime.now(),
            }
            state.stage_timings = stage_timings
            raise WorkflowStageError(
                stage=stage,
                failure_category=_failure_category(stage, exc),
                failure_type=type(exc).__name__,
                stage_timings=stage_timings,
                review_state=_failed_review_state(state, stage),
            ) from exc

    return invoke


def _failed_review_state(state: AgentState, stage: str) -> dict | None:
    """Safe decision metadata for a failed trace; no feedback/content."""
    review_stages = ("reviewer", "revision", "reviewer_final")
    if (
        stage not in review_stages
        and state.initial_review_decision is None
        and state.revision_count == 0
    ):
        return None
    return {
        "initial_decision": state.initial_review_decision,
        "revision_attempted": (
            state.revision_count > 0 or stage in ("revision", "reviewer_final")
        ),
        "revision_count": state.revision_count,
        "final_decision": None,
        "final_feedback": None,
        "outcome": None,
    }


def _failure_category(stage: str, error: Exception) -> str:
    if isinstance(error, RetrievalUnavailableError):
        return "retrieval_unavailable"
    if isinstance(error, InvalidToolSelectionError):
        return "invalid_tool_selection"
    if isinstance(error, ToolExecutionError):
        return "tool_execution_error"
    if isinstance(error, (TimeoutError, openai.APITimeoutError)):
        return "operation_timeout"
    return f"{stage}_failure"


def route_after_review(state: AgentState) -> str:
    """Route to the single revision step only when it is explicitly allowed.

    The revision budget is enforced here, not in prompt text: even if the
    reviewer asks for another revision on the final pass, the graph ends.
    """
    revision_feedback = state.revision_feedback or ""

    if (
        state.revision_enabled
        and state.selected_tool not in (None, "none")
        and state.review_decision == "revise"
        and state.revision_count < 1
        and revision_feedback.strip()
    ):
        return "revision"
    return "end"


def get_graph():
    """Construct and compile the graph workflow."""
    logger.debug("graph_construction_started")

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes with appropriate error handling
    logger.debug("adding_workflow_nodes")
    workflow.add_node("planner", _stage_node("planner", planner_node))
    workflow.add_node("worker", _stage_node("worker", worker_node))
    workflow.add_node("reviewer", _stage_node("reviewer", reviewer_node))
    workflow.add_node("revision", _stage_node("revision", revision_node))
    workflow.add_node("reviewer_final", _stage_node("reviewer_final", reviewer_node))

    # Add only the essential edges
    logger.debug("adding_workflow_edges")
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "worker")
    workflow.add_edge("worker", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"revision": "revision", "end": END},
    )
    workflow.add_edge("revision", "reviewer_final")
    workflow.add_edge("reviewer_final", END)

    # Compile graph
    logger.debug("compiling_graph")
    app = workflow.compile()

    logger.info(
        "graph_construction_completed",
        nodes_count=5,
        has_checkpointer=False
    )

    return app
