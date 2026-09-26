"""Unit tests for the POST /ask route (app.api.routes.ask).

Builds a minimal FastAPI app around just the ask router (not
app.api.main's lifespan, which would boot the real runtime/vector
store), with app.state.runtime replaced by a mock. This exercises
request validation, response shaping, and error translation - the
route's actual job - without any LLM calls or graph execution.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ask
from app.contracts.response import QueryResponse
from app.contracts.trace import ExecutionTrace


def make_app(mock_runtime):
    app = FastAPI()
    app.state.runtime = mock_runtime
    app.include_router(ask.router)
    return app


def make_query_response(**overrides) -> QueryResponse:
    base = dict(
        user_input="hello",
        plan="a plan",
        selected_tool="none",
        tool_input={},
        tool_output="hi",
        draft_answer="Tool result:\nhi",
        final_answer="hi there",
        review_feedback="looks good",
        retrieved_sources=None,
        execution_trace=ExecutionTrace(
            trace_id="trace-1",
            started_at=None,
            ended_at=None,
            duration_ms=None,
            planner_events=[],
            worker_events=[],
            reviewer_events=[],
            retrieval_trace=None,
            final_answer="hi there",
        ),
    )
    base.update(overrides)
    return QueryResponse(**base)


@pytest.mark.unit
class TestAskRoute:
    def test_returns_the_final_answer_trace_id_and_sources(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.run_question.return_value = make_query_response(
            final_answer="the answer", retrieved_sources=["a.md"]
        )
        client = TestClient(make_app(mock_runtime))

        response = client.post("/ask", json={"question": "How does X work?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "the answer"
        assert body["sources"] == ["a.md"]
        assert body["trace_id"] == "trace-1"

    def test_passes_the_question_and_trace_id_through_to_the_runtime(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.run_question.return_value = make_query_response()
        client = TestClient(make_app(mock_runtime))

        client.post("/ask", json={"question": "hello", "trace_id": "caller-supplied"})

        mock_runtime.run_question.assert_called_once_with("hello", "caller-supplied")

    def test_rejects_an_empty_question_with_a_422(self, mocker):
        mock_runtime = mocker.Mock()
        client = TestClient(make_app(mock_runtime))

        response = client.post("/ask", json={"question": ""})

        assert response.status_code == 422
        mock_runtime.run_question.assert_not_called()

    def test_translates_a_runtime_exception_into_a_500_without_leaking_details(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.run_question.side_effect = RuntimeError("graph exploded with a secret path")
        client = TestClient(make_app(mock_runtime))

        response = client.post("/ask", json={"question": "hello"})

        assert response.status_code == 500
        assert "graph exploded" not in response.json()["detail"]

    def test_falls_back_to_the_caller_supplied_trace_id_when_no_execution_trace_is_returned(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.run_question.return_value = make_query_response(execution_trace=None)
        client = TestClient(make_app(mock_runtime))

        response = client.post("/ask", json={"question": "hello", "trace_id": "caller-id"})

        assert response.json()["trace_id"] == "caller-id"
