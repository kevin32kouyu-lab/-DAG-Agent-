from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_trace_insight_not_found():
    resp = client.get("/api/trace/test_task/insight_nonexistent")
    assert resp.status_code == 404


def test_trace_insight_with_steps():
    resp = client.get("/api/trace/test_task/insight_1?include_steps=true")
    assert resp.status_code in (200, 404)
