from datetime import datetime
from src.infrastructure.snapshot import SnapshotStore
from src.dag.models import NodeSnapshot, NodeState


def test_save_and_load_snapshot():
    store = SnapshotStore(":memory:")
    snap = NodeSnapshot(
        task_id="task1", node_id="node1",
        state=NodeState.COMPLETED,
        kg_changeset={"nodes": ["n1", "n2"], "edges": ["e1"]},
        checkpoint_time=datetime.now(),
        llm_cost=0.05,
    )
    store.save(snap)
    loaded = store.load("task1")
    assert loaded is not None
    assert "node1" in loaded
    assert loaded["node1"].state == NodeState.COMPLETED
    assert loaded["node1"].task_id == "task1"
    assert loaded["node1"].llm_cost == 0.05
    assert loaded["node1"].kg_changeset["nodes"] == ["n1", "n2"]


def test_save_multiple_snapshots_same_task():
    store = SnapshotStore(":memory:")
    store.save(NodeSnapshot(task_id="t1", node_id="n1", state=NodeState.COMPLETED))
    store.save(NodeSnapshot(task_id="t1", node_id="n2", state=NodeState.RUNNING))
    loaded = store.load("t1")
    assert len(loaded) == 2
    assert loaded["n1"].state == NodeState.COMPLETED
    assert loaded["n2"].state == NodeState.RUNNING


def test_save_overwrites_existing():
    store = SnapshotStore(":memory:")
    store.save(NodeSnapshot(task_id="t1", node_id="n1", state=NodeState.RUNNING))
    store.save(NodeSnapshot(task_id="t1", node_id="n1", state=NodeState.COMPLETED))
    loaded = store.load("t1")
    assert loaded["n1"].state == NodeState.COMPLETED


def test_load_nonexistent_task():
    store = SnapshotStore(":memory:")
    assert store.load("nonexistent") is None


def test_snapshot_stores_all_states():
    store = SnapshotStore(":memory:")
    for state in NodeState:
        store.save(NodeSnapshot(task_id="states", node_id=f"node_{state.value}", state=state))
    loaded = store.load("states")
    for state in NodeState:
        assert loaded[f"node_{state.value}"].state == state
