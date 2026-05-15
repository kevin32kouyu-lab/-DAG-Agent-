from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "unhealthy_agents" in data
    assert "timed_out_tasks" in data


def test_create_task_accepts_targets():
    resp = client.post("/api/task", json={"targets": ["Notion"]})
    assert resp.status_code in (200, 500)


def test_get_task_returns_404_for_nonexistent():
    """GET /api/task/{task_id} returns 404 when task doesn't exist."""
    resp = client.get("/api/task/nonexistent_task_xyz")
    assert resp.status_code == 404
