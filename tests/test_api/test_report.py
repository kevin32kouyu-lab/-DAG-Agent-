from fastapi.testclient import TestClient
from src.api.app import app
from src.api.routes.report import _collect_evidence_sources

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


def test_get_report_pdf_format():
    resp = client.get("/api/report/test_task_1?format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0
    assert resp.content[:5] == b"%PDF-"


class FailingTraceStore:
    def trace_upstream(self, node_id, max_depth):
        raise RuntimeError("trace failed")


def test_collect_evidence_sources_logs_trace_failure(caplog):
    result = _collect_evidence_sources(FailingTraceStore(), "node_1", max_depth=3)

    assert result == []
    assert "证据链读取失败" in caplog.text
