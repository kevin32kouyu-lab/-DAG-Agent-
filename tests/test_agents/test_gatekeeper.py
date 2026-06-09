import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.deps import get_scheduler, get_store
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.knowledge_graph.models import SourceInfoNode, NodeType

client = TestClient(app)


def test_gatekeeper_get_and_approve_sources():
    scheduler = get_scheduler()

    # 1. Create a mock DAG with Collector node (refactored: no separate SourceDiscovery)
    n_col = DAGNode(
        node_id="collector",
        agent_type="Collector",
        input_query={},
        state=NodeState.COMPLETED
    )
    # Populate discovered URLs in the context _output_data
    n_col.context["_output_data"] = {
        "summary": "Mocked collection",
        "data": {
            "urls": [
                "https://example.com/target1",
                "https://example.com/target2"
            ]
        }
    }

    n_report = DAGNode(
        node_id="report",
        agent_type="ReportGenerator",
        input_query={"urls": []},
        state=NodeState.PENDING,
        depends_on=["collector"]
    )

    import uuid
    task_id = f"task_gatekeeper_ut_{uuid.uuid4().hex[:8]}"
    dag = TaskDAG(
        task_id=task_id,
        nodes=[n_col, n_report],
        targets=["TargetProduct"]
    )

    # Register the DAG in the scheduler
    scheduler._dag_registry[task_id] = dag

    # 2. Test GET /api/task/{task_id}/sources
    resp = client.get(f"/api/task/{task_id}/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert sorted(data["sources"]) == [
        "https://example.com/target1",
        "https://example.com/target2"
    ]

    # 3. Add a SourceInfo node to graph and verify it is retrieved too
    store = get_store()
    src_node = SourceInfoNode(
        url="https://example.com/target3",
        domain="example.com",
        metadata={"task_id": task_id}
    )
    store.create_node(src_node)

    resp2 = client.get(f"/api/task/{task_id}/sources")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert sorted(data2["sources"]) == [
        "https://example.com/target1",
        "https://example.com/target2",
        "https://example.com/target3"
    ]

    # 4. Test POST /api/task/{task_id}/sources/approve
    approve_payload = {"urls": ["https://example.com/target1", "https://example.com/target3"]}
    resp_app = client.post(f"/api/task/{task_id}/sources/approve", json=approve_payload)
    assert resp_app.status_code == 200
    app_data = resp_app.json()
    assert app_data["status"] == "approved"
    assert app_data["urls_count"] == 2

    # Verify collector node's input query is updated
    assert n_col.input_query["urls"] == [
        "https://example.com/target1",
        "https://example.com/target3"
    ]
