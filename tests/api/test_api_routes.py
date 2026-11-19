import pytest


@pytest.mark.unit
def test_registers_the_documented_api_routes():
    from app.api.main import app

    paths = app.openapi()["paths"]

    assert "post" in paths["/ask"]
    assert "get" in paths["/health"]
    assert "post" in paths["/evaluate"]
    assert "get" in paths["/trace/{trace_id}"]
