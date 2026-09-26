"""Unit tests for the worker_node() seam in app.agents.worker.

worker_node(state: AgentState) -> AgentState is the module's only public
interface and its only real caller (app.agents.graph). Each registry
entry's "invoke" adapter is mocked at the app.agents.worker.TOOLS
boundary (the name worker_node actually looks up), never invoking a
real tool, since worker_node's job is dispatch, not tool correctness
(that belongs to each tool's own tests and to app.tools.registry's
adapters).
"""
import pytest

from app.agents.worker import worker_node
from app.contracts.agent import AgentState
from app.contracts.trace import RetrievalTrace


def make_state(selected_tool: str, tool_input: dict | None = None, user_input: str = "hello") -> AgentState:
    return AgentState(
        user_input=user_input,
        selected_tool=selected_tool,
        tool_input=tool_input,
        trace_id="trace-1",
    )


def fake_tools(invoke_fn) -> dict:
    return {"code_explainer": {"invoke": invoke_fn}}


@pytest.mark.unit
class TestWorkerNodeDispatch:
    def test_dispatches_through_the_registrys_invoke_adapter(self, mocker):
        mocker.patch(
            "app.agents.worker.TOOLS",
            {"code_explainer": {"invoke": mocker.Mock(return_value={
                "result": "explained", "sources": None, "retrieval_trace": None
            })}},
        )
        state = make_state("code_explainer", tool_input={"code": "print(1)"})

        result = worker_node(state)

        assert result.tool_output == "explained"
        assert result.draft_answer == "Tool result:\nexplained"
        assert result.retrieved_sources is None
        assert result.retrieval_trace is None

    def test_passes_tool_input_and_user_input_to_the_invoke_adapter(self, mocker):
        invoke_mock = mocker.Mock(return_value={"result": "x", "sources": None, "retrieval_trace": None})
        mocker.patch("app.agents.worker.TOOLS", {"code_explainer": {"invoke": invoke_mock}})
        state = make_state("code_explainer", tool_input={"code": "print(1)"}, user_input="hello")

        worker_node(state)

        invoke_mock.assert_called_once_with({"code": "print(1)"}, "hello")

    def test_surfaces_sources_and_retrieval_trace_from_the_invoke_result(self, mocker):
        trace = RetrievalTrace(query="q")
        mocker.patch(
            "app.agents.worker.TOOLS",
            {"doc_retriever": {"invoke": mocker.Mock(return_value={
                "result": "the context", "sources": ["a.md", "b.md"], "retrieval_trace": trace
            })}},
        )
        state = make_state("doc_retriever", tool_input={"query": "what is X?"})

        result = worker_node(state)

        assert result.tool_output == "the context"
        assert result.retrieved_sources == ["a.md", "b.md"]
        assert result.retrieval_trace is trace

    def test_none_tool_passes_user_input_through_without_invoking_a_tool(self):
        """Regression test: selected_tool == "none" previously had no
        dispatch branch in worker_node, silently falling into the
        "unknown tool" error path and showing the user an error message
        instead of a direct answer, even though "none" is a valid,
        documented selection (see TOOLS["none"]'s description: "Use for
        general questions that don't require any specific tool"). This
        test exercises the real app.tools.registry.TOOLS["none"] entry,
        not a mock, since "none"'s behavior (pass-through, no tool call)
        is itself the thing under test."""
        state = make_state("none", tool_input={}, user_input="what's 2+2?")

        result = worker_node(state)

        assert "Error" not in result.tool_output
        assert result.draft_answer == "Tool result:\nwhat's 2+2?"

    def test_unknown_tool_produces_an_error_result_without_raising(self):
        state = make_state("not_a_real_tool")

        result = worker_node(state)

        assert "Error" in result.tool_output
        assert "not_a_real_tool" in result.tool_output

    def test_tool_exception_is_caught_and_reported_as_an_error_result(self, mocker):
        mocker.patch(
            "app.agents.worker.TOOLS",
            {"doc_retriever": {"invoke": mocker.Mock(side_effect=RuntimeError("boom"))}},
        )
        state = make_state("doc_retriever", tool_input={"query": "x"})

        result = worker_node(state)

        assert "Error" in result.tool_output
        assert "boom" in result.tool_output

    def test_records_stage_timings(self, mocker):
        mocker.patch(
            "app.agents.worker.TOOLS",
            {"code_explainer": {"invoke": mocker.Mock(return_value={
                "result": "x", "sources": None, "retrieval_trace": None
            })}},
        )
        state = make_state("code_explainer", tool_input={"code": "x"})

        result = worker_node(state)

        assert "worker" in result.stage_timings
        assert "started_at" in result.stage_timings["worker"]
        assert "ended_at" in result.stage_timings["worker"]
