import uuid
import structlog
from dotenv import load_dotenv
from app.agents.graph import get_graph
from app.config.logging_config import configure_logging
from app.config.env_validator import validate_environment

# Load environment variables
load_dotenv()

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

def main():
    """Main function to run the AI assistant workflow."""
    # Generate correlation ID for this email processing session
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    logger.info(
        "ai_assistant_started",
        correlation_id=correlation_id,
        workflow="ai_assistant_handler"
    )

    # Test with an urgent billing issue
    initial_state = {
        # "input": "Explain code snippet in Java: ```public class HelloWorld { public static void main(String[] args) { System.out.println(\"Hello, World!\"); } }```",
        "input": "How to define an AWS RDS single instance? ",
        "messages": []
    }

    logger.info(
        "initial_state_created",
        input=initial_state["input"],
        content_length=len(initial_state["input"])
    )

    # Run with a thread_id for persistence
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
            output=final_result.get("output"),
        )
        logger.info("question_answered_successfully")
    except Exception as e:
        logger.error(
            "workflow_resume_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        raise

    save_graph_image(graph)

def save_graph_image(graph):
    """Generate and save a visualization of the graph to a PNG file."""
    try:
        logger.info("generating_graph_visualization")
        # Generate the image data
        graph_image = graph.get_graph().draw_mermaid_png()

        # Save the image to a file
        with open("graph_image.png", "wb") as f:
            f.write(graph_image)

        logger.info("graph_image_saved", filename="graph_image.png")
    except Exception as e:
        logger.warning(
            "graph_visualization_failed",
            error=str(e),
            error_type=type(e).__name__,
            message="Optional dependency for image rendering may be missing"
        )

if __name__ == "__main__":
    main()
