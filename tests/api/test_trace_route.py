import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.trace import router as trace_router


def make_app(mock_runtime):
    app = FastAPI()
    app.state.runtime = mock_runtime
    app.include_router(trace_router)
    return app


@pytest.mark.unit
class TestTraceRoute:
    def test_returns_the_full_trace_for_a_known_trace_id(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.get_trace.return_value = {
            "trace_id": "trace-123",
            "final_answer": "Grounded answer",
            "outcome": "success",
        }
        client = TestClient(make_app(mock_runtime))

        response = client.get("/trace/trace-123")

        assert response.status_code == 200
        assert response.json() == {
            "trace_id": "trace-123",
            "execution_trace": {
                "trace_id": "trace-123",
                "final_answer": "Grounded answer",
                "outcome": "success",
            },
        }
        mock_runtime.get_trace.assert_called_once_with("trace-123")

    def test_returns_not_found_for_an_unknown_or_expired_trace(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.get_trace.return_value = None
        client = TestClient(make_app(mock_runtime))

        response = client.get("/trace/missing")

        assert response.status_code == 404
        assert response.json()["detail"] == "Execution trace not found."

    def test_hides_trace_store_errors_from_the_caller(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.get_trace.side_effect = OSError("private filesystem path")
        client = TestClient(make_app(mock_runtime))

        response = client.get("/trace/trace-123")

        assert response.status_code == 500
        assert "private filesystem path" not in response.text
