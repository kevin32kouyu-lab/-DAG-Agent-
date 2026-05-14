from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_get_report_returns_sections():
    resp = client.get("/api/report/test_task_1")
    assert resp.status_code == 200
    data = resp.json()
    assert "sections" in data


def test_get_report_json_format():
    resp = client.get("/api/report/test_task_1?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "json"
    assert "sections" in data
