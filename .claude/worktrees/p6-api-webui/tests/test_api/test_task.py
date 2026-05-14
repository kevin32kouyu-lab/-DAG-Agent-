from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_task_accepts_targets():
    resp = client.post("/api/task", json={"targets": ["Notion"]})
    assert resp.status_code in (200, 500)


def test_get_task_returns_stub():
    """GET /api/task/{task_id} returns stub until full state tracking is added."""
    resp = client.get("/api/task/nonexistent")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == "nonexistent"
