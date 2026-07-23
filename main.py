import argparse
import json
import structlog

from app.runtime.assistant_runtime import AssistantRuntime

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


def save_graph_image():
    """Generate and save a visualization of the graph to a PNG file."""
    try:
        from app.agents.graph import get_graph

        logger.debug("generating_graph_visualization")
        graph = get_graph()
        graph_image = graph.get_graph().draw_mermaid_png()

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


def main():
    """CLI entry point for the AI assistant.

    Creates an AssistantRuntime, handles user interaction (args or interactive
    prompt), runs the question, and displays the result.
    """
    args = parse_args()

    runtime = AssistantRuntime()
    runtime.setup()

    logger.info(
        "ai_assistant_started",
        workflow="ai_assistant_handler"
    )

    # Get question from CLI arg or interactive prompt
    if args.question:
        user_question = args.question
    else:
        logger.info("ai_assistant_banner", banner="\U0001f916 AI Assistant - Multi-Agent")
        user_question = input("\n\U0001f4ac Enter your technical question: ").strip()

    if not user_question:
        logger.warning("empty_input_provided", message="No question provided. Exiting.")
        return

    response = runtime.run_question(user_question)

    if args.json:
        print(json.dumps(response.to_dict()))
    else:
        save_graph_image()


if __name__ == "__main__":
    main()
