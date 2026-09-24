"""Unit tests for app.runtime.assistant_runtime.AssistantRuntime.

AssistantRuntime.setup() and .run_question() are the two public seams.
setup() imports its heavy dependencies (env validation, logging config,
vector store, graph compilation) inside the function body "to avoid
side effects at module load time", so each is mocked at its own
defining module, not at assistant_runtime's import site.
"""
import pytest

from app.contracts.agent import AgentState
from app.runtime.assistant_runtime import AssistantRuntime


@pytest.fixture
def mock_setup_dependencies(mocker):
    """Mock every dependency AssistantRuntime.setup() imports internally."""
    mocker.patch("app.config.env_validator.validate_environment", return_value={})
    mocker.patch("app.config.logging_config.configure_logging")
    mocker.patch("app.rag.vector_store.initialize_vector_store")
    mock_graph = mocker.Mock()
    mocker.patch("app.agents.graph.get_graph", return_value=mock_graph)
    return mock_graph


@pytest.mark.unit
class TestAssistantRuntimeSetup:
    def test_setup_initializes_the_runtime_and_compiles_the_graph(self, mock_setup_dependencies):
        runtime = AssistantRuntime()

        result = runtime.setup()

        assert result is True
        assert runtime._is_initialized is True
        assert runtime.graph is mock_setup_dependencies

    def test_setup_propagates_validation_errors_without_marking_initialized(self, mocker):
        mocker.patch(
            "app.config.env_validator.validate_environment",
            side_effect=RuntimeError("missing OPENAI_API_KEY"),
        )
        runtime = AssistantRuntime()

        with pytest.raises(RuntimeError, match="missing OPENAI_API_KEY"):
            runtime.setup()

        assert runtime._is_initialized is False


@pytest.mark.unit
class TestAssistantRuntimeRunQuestion:
    def _final_result(self, **overrides):
        base = {
            "user_input": "hello",
            "plan": "a plan",
            "selected_tool": "none",
            "tool_input": {},
            "tool_output": "hello",
            "draft_answer": "Tool result:\nhello",
            "final_answer": "hi there",
            "review_feedback": "looks good",
            "retrieved_sources": None,
        }
        base.update(overrides)
        return base

    def test_calls_setup_automatically_when_not_yet_initialized(self, mock_setup_dependencies, mocker):
        mock_setup_dependencies.invoke.return_value = self._final_result()
        mocker.patch("app.runtime.assistant_runtime.build_execution_trace", return_value=mocker.Mock(trace_id="t-1"))
        runtime = AssistantRuntime()
        assert runtime._is_initialized is False

        runtime.run_question("hello")

        assert runtime._is_initialized is True

    def test_generates_a_trace_id_when_none_is_provided(self, mocker):
        runtime = AssistantRuntime()
        runtime._is_initialized = True
        runtime.graph = mocker.Mock()
        runtime.graph.invoke.return_value = self._final_result()
        mocker.patch("app.runtime.assistant_runtime.build_execution_trace", return_value=mocker.Mock(trace_id="generated"))

        response = runtime.run_question("hello")

        invoked_state: AgentState = runtime.graph.invoke.call_args[0][0]
        assert invoked_state.trace_id  # non-empty, generated
        assert response.execution_trace.trace_id == "generated"

    def test_reuses_a_caller_supplied_trace_id_as_the_thread_id(self, mocker):
        runtime = AssistantRuntime()
        runtime._is_initialized = True
        runtime.graph = mocker.Mock()
        runtime.graph.invoke.return_value = self._final_result()
        mocker.patch("app.runtime.assistant_runtime.build_execution_trace", return_value=mocker.Mock(trace_id="trace-42"))

        runtime.run_question("hello", trace_id="trace-42")

        invoked_state: AgentState = runtime.graph.invoke.call_args[0][0]
        config = runtime.graph.invoke.call_args[0][1]
        assert invoked_state.trace_id == "trace-42"
        assert config["configurable"]["thread_id"] == "trace-42"

    def test_returns_a_query_response_built_from_the_final_graph_state(self, mocker):
        runtime = AssistantRuntime()
        runtime._is_initialized = True
        runtime.graph = mocker.Mock()
        runtime.graph.invoke.return_value = self._final_result(
            final_answer="the answer", retrieved_sources=["a.md"]
        )
        mocker.patch("app.runtime.assistant_runtime.build_execution_trace", return_value=mocker.Mock(trace_id="t-1"))

        response = runtime.run_question("hello", trace_id="t-1")

        assert response.final_answer == "the answer"
        assert response.retrieved_sources == ["a.md"]
        assert response.execution_trace.trace_id == "t-1"

    def test_reraises_graph_invocation_errors(self, mocker):
        runtime = AssistantRuntime()
        runtime._is_initialized = True
        runtime.graph = mocker.Mock()
        runtime.graph.invoke.side_effect = RuntimeError("graph exploded")

        with pytest.raises(RuntimeError, match="graph exploded"):
            runtime.run_question("hello", trace_id="t-1")
