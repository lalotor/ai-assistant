import argparse
import json
import uuid
import structlog
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
# This ensures all modules can access environment variables when imported
load_dotenv()

from app.agents.graph import get_graph
from app.contracts.agent import AgentState
from app.config.logging_config import configure_logging
from app.config.env_validator import validate_environment
from app.rag.vector_store import initialize_vector_store

# Validate environment variables before proceeding
# This ensures all required configuration is present
validated_env = validate_environment(verbose=True)

# Configure logging from environment variables
configure_logging(
    log_level=validated_env.get("LOG_LEVEL", "INFO"),
    json_logs=validated_env.get("JSON_LOGS", "false").lower() == "true",
    enable_file_logging=validated_env.get("ENABLE_FILE_LOGGING", "false").lower() == "true",
    log_file_path=validated_env.get("LOG_FILE_PATH", "logs/app.log")
)

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="AI Assistant - Multi-Agent")
    parser.add_argument(
        "-q", "--question",
        type=str,
        default=None,
        help="Question to ask the assistant (skips interactive prompt)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output the result as JSON to stdout"
    )
    return parser.parse_args()


def run_question(question: str, *, output_json: bool = False) -> dict:
    """Run a single question through the AI assistant graph.

    Args:
        question: The user question to process.
        output_json: If True, print the result as JSON to stdout.

    Returns:
        The final graph state as a dictionary.
    """
    initial_state = AgentState(user_input=question)

    logger.info(
        "initial_state_created",
        input=initial_state.user_input,
        content_length=len(initial_state.user_input)
    )

    config = {"configurable": {"thread_id": "user_123"}}

    logger.info(
        "graph_initialization",
        thread_id=config["configurable"]["thread_id"]
    )

    try:
        graph = get_graph()
        logger.info("graph_compiled_successfully")

        final_result = graph.invoke(initial_state, config)
        logger.info(
            "question_answered",
            user_input=final_result["user_input"],
            plan=final_result["plan"],
            final_answer=final_result["final_answer"],
            review_feedback=final_result["review_feedback"]
        )
        logger.debug("question_answered_successfully")
    except Exception as e:
        logger.error(
            "workflow_resume_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise

    if output_json:
        output = {
            "user_input": final_result["user_input"],
            "plan": final_result["plan"],
            "final_answer": final_result["final_answer"],
            "review_feedback": final_result["review_feedback"]
        }
        print(json.dumps(output))

    return final_result


def main():
    """Main function to run the AI assistant workflow."""
    args = parse_args()

    logger.info("initializing_vector_store")
    initialize_vector_store()
    logger.info("vector_store_ready")

    # Generate correlation ID for this session
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    logger.info(
        "ai_assistant_started",
        correlation_id=correlation_id,
        workflow="ai_assistant_handler"
    )

    # Get question from CLI arg or interactive prompt
    if args.question:
        user_question = args.question
    else:
        print("\n" + "="*60)
        print("🤖 AI Assistant - Multi-Agent")
        print("="*60)
        user_question = input("\n💬 Enter your technical question: ").strip()

    if not user_question:
        logger.warning("empty_input_provided")
        print("\n⚠️  No question provided. Exiting...")
        return

    run_question(user_question, output_json=args.json)

    if not args.json:
        save_graph_image(get_graph())

def save_graph_image(graph):
    """Generate and save a visualization of the graph to a PNG file."""
    try:
        logger.debug("generating_graph_visualization")
        # Generate the image data
        graph_image = graph.get_graph().draw_mermaid_png()

        # Save the image to a file
        with open("graph_image.png", "wb") as f:
            f.write(graph_image)

        logger.debug("graph_image_saved", filename="graph_image.png")
    except Exception as e:
        logger.warning(
            "graph_visualization_failed",
            error=str(e),
            error_type=type(e).__name__,
            message="Optional dependency for image rendering may be missing"
        )

if __name__ == "__main__":
    main()
