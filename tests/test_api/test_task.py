from fastapi.testclient import TestClient
from src.api.app import app
from src.api.routes.task import CreateTaskRequest, _persist_task_targets

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


def test_create_task_request_defaults_to_template_planning():
    req = CreateTaskRequest(targets=["Notion", "ClickUp"], industry="saas")

    assert req.planning_mode == "template"
    assert req.industry == "saas"


def test_create_task_request_accepts_legacy_orchestrator_planning():
    req = CreateTaskRequest(
        targets=["Notion", "ClickUp"],
        industry="saas",
        planning_mode="orchestrator",
    )

    assert req.planning_mode == "orchestrator"


def test_persist_task_targets_preserves_existing_targets(tmp_path):
    targets_file = tmp_path / "task_targets.json"
    targets_file.write_text('{"old_task": ["Old"]}', encoding="utf-8")

    _persist_task_targets("new_task", ["Notion", "Linear"], targets_file=targets_file)

    content = targets_file.read_text(encoding="utf-8")
    assert '"old_task"' in content
    assert '"new_task"' in content
    assert "Notion" in content
    assert "Linear" in content


def test_persist_task_targets_logs_corrupted_file(tmp_path, caplog):
    targets_file = tmp_path / "task_targets.json"
    targets_file.write_text("{bad json", encoding="utf-8")

    _persist_task_targets("new_task", ["Notion"], targets_file=targets_file)

    assert "任务目标缓存读取失败" in caplog.text
    assert "new_task" in targets_file.read_text(encoding="utf-8")
