import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.evaluate import router as evaluate_router


def make_app(mock_runtime):
    app = FastAPI()
    app.state.runtime = mock_runtime
    app.include_router(evaluate_router)
    return app


@pytest.mark.unit
class TestEvaluateRoute:
    def test_runs_the_selected_dataset_and_returns_metrics_and_results(self, mocker):
        evaluation = {
            "dataset": "smoke",
            "revision_enabled": True,
            "results_file": "evaluation/results/eval_api_smoke_revision.json",
            "summary": {"questions": 1, "evaluated": 1},
            "status_counts": {"pass": 1},
            "results": [{"question": "What is X?", "status": "pass", "score": 1.0}],
        }
        mock_runtime = mocker.Mock()
        mock_runtime.run_evaluation.return_value = evaluation
        client = TestClient(make_app(mock_runtime))

        response = client.post(
            "/evaluate",
            json={"dataset": "smoke", "revision_enabled": True},
        )

        assert response.status_code == 200
        assert response.json() == evaluation
        mock_runtime.run_evaluation.assert_called_once_with(
            "smoke", revision_enabled=True
        )

    def test_rejects_unregistered_dataset_names(self, mocker):
        mock_runtime = mocker.Mock()
        client = TestClient(make_app(mock_runtime))

        response = client.post("/evaluate", json={"dataset": "../../private.json"})

        assert response.status_code == 422
        mock_runtime.run_evaluation.assert_not_called()

    def test_hides_unexpected_evaluation_errors(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime.run_evaluation.side_effect = RuntimeError("private API credential")
        client = TestClient(make_app(mock_runtime))

        response = client.post("/evaluate", json={"dataset": "smoke"})

        assert response.status_code == 500
        assert "private API credential" not in response.text
