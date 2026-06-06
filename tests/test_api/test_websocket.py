from fastapi.testclient import TestClient
from src.api.app import app
from src.api.websocket import _broadcast, active_connections

client = TestClient(app)

def test_websocket_endpoint_registered():
    """Verify the WebSocket route is registered — TestClient can't fully test WS, but we verify the route exists."""
    # TestClient doesn't support WebSocket natively; verify app has the route
    routes = [r.path for r in app.routes]
    assert "/ws/task/{task_id}" in routes


class WorkingConnection:
    def __init__(self):
        self.events = []

    async def send_json(self, event):
        self.events.append(event)


class FailingConnection:
    async def send_json(self, event):
        raise RuntimeError("connection closed")


async def test_broadcast_removes_failed_connections(caplog):
    task_id = "task_ws_cleanup"
    event = {"event": "node_completed"}
    working = WorkingConnection()
    failing = FailingConnection()
    active_connections[task_id] = [working, failing]

    await _broadcast(task_id, event)

    assert working.events == [event]
    assert active_connections[task_id] == [working]
    assert "WebSocket 广播失败" in caplog.text
