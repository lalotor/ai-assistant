import uuid
import structlog
from dotenv import load_dotenv

from app.contracts.response import QueryResponse
from app.contracts.agent import AgentState
from app.tracing import build_execution_trace

logger = structlog.get_logger(__name__)


class AssistantRuntime:
    """Core runtime engine for the AI assistant.

    Provides a reusable, interface-agnostic entry point for running questions
    through the multi-agent graph. Can be consumed by CLI, REST API, or any
    other interface without duplicating setup or orchestration logic.
    """

    def __init__(self):
        self._is_initialized = False

    def setup(self) -> bool:
        """Initialize all required dependencies for the runtime.

        Loads environment variables, validates configuration, configures
        structured logging, and initializes the vector store.

        Returns:
            True if setup completed successfully.

        Raises:
            Exception: If environment validation or vector store initialization fails.
        """
        load_dotenv()

        # Import here to avoid side effects at module load time
        from app.config.env_validator import validate_environment
        from app.config.logging_config import configure_logging
        from app.rag.vector_store import initialize_vector_store

        validated_env = validate_environment(verbose=True)

        configure_logging(
            log_level=validated_env.get("LOG_LEVEL", "INFO"),
            json_logs=validated_env.get("JSON_LOGS", "false").lower() == "true",
            enable_file_logging=validated_env.get("ENABLE_FILE_LOGGING", "false").lower() == "true",
            log_file_path=validated_env.get("LOG_FILE_PATH", "logs/app.log")
        )

        logger.info("initializing_vector_store")
        initialize_vector_store()
        logger.info("vector_store_ready")

        self._is_initialized = True
        return True

    def run_question(self, question: str, trace_id: str = None) -> QueryResponse:
        """Run a single question through the AI assistant graph.

        If the setup method has not been called, it will use the default setup.
        Exception handling is done in the run_question function, so any
        exceptions raised will be logged and re-raised.

        Args:
            question: The user question to process.
            trace_id: The ID for tracing this execution. If not provided,
                a new trace ID will be generated.

        Returns:
            The final graph state as a QueryResponse object.

        Raises:
            Exception: If graph compilation or invocation fails.
        """
        if not self._is_initialized:
            self.setup()

        # Import here to avoid side effects at module load time
        from app.agents.graph import get_graph

        # Generate trace_id if not provided
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        # Bind correlation ID for structured logging on this question
        structlog.contextvars.bind_contextvars(correlation_id=trace_id)

        initial_state = AgentState(user_input=question, trace_id=trace_id)

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
                review_feedback=final_result["review_feedback"],
                retrieved_sources=final_result.get("retrieved_sources")
            )
            logger.debug("question_answered_successfully")

            trace = build_execution_trace(final_result)
            logger.info(
                "execution_trace_built",
                trace_id=trace.trace_id
            )
        except Exception as e:
            logger.error(
                "workflow_execution_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise

        return QueryResponse(
            user_input=final_result["user_input"],
            plan=final_result["plan"],
            selected_tool=final_result.get("selected_tool"),
            tool_input=final_result.get("tool_input"),
            tool_output=final_result.get("tool_output"),
            draft_answer=final_result.get("draft_answer"),
            final_answer=final_result["final_answer"],
            review_feedback=final_result["review_feedback"],
            retrieved_sources=final_result.get("retrieved_sources"),
            execution_trace=trace
        )
