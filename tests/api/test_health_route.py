"""Unit tests for the GET /health route (app.api.routes.health)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import health


def make_app(mock_runtime):
    app = FastAPI()
    app.state.runtime = mock_runtime
    app.include_router(health.router)
    return app


@pytest.mark.unit
class TestHealthRoute:
    def test_reports_not_initialized_before_runtime_setup(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime._is_initialized = False
        client = TestClient(make_app(mock_runtime))

        response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["runtime_initialized"] is False

    def test_reports_initialized_after_runtime_setup(self, mocker):
        mock_runtime = mocker.Mock()
        mock_runtime._is_initialized = True
        client = TestClient(make_app(mock_runtime))

        response = client.get("/health")

        assert response.json()["runtime_initialized"] is True
