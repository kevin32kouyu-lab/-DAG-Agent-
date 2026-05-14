import pytest
from src.dag.models import DAGNode, TaskDAG, NodeState


def test_dag_node_initial_state():
    node = DAGNode(
        node_id="collector_1",
        agent_type="Collector",
        input_query={"url": "https://example.com"},
        depends_on=[],
    )
    assert node.state == NodeState.PENDING
    assert node.retries == 0
    assert node.max_retries == 3


def test_dag_node_state_transitions():
    node = DAGNode(node_id="n1", agent_type="Test", input_query={}, depends_on=[])
    node.state = NodeState.READY
    node.state = NodeState.RUNNING
    node.state = NodeState.COMPLETED
    assert node.state == NodeState.COMPLETED


def test_task_dag_get_ready_nodes():
    n1 = DAGNode(node_id="source_disc", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="collector_1", agent_type="Collector", input_query={}, depends_on=["source_disc"])
    n3 = DAGNode(node_id="collector_2", agent_type="Collector", input_query={}, depends_on=["source_disc"])
    n1.state = NodeState.COMPLETED

    dag = TaskDAG(task_id="task_1", nodes=[n1, n2, n3])
    ready = dag.get_ready_nodes()
    assert len(ready) == 2
    assert {n.node_id for n in ready} == {"collector_1", "collector_2"}


def test_task_dag_is_terminal():
    n1 = DAGNode(node_id="n1", agent_type="Test", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="Test", input_query={}, depends_on=["n1"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2])

    n1.state = NodeState.COMPLETED
    n2.state = NodeState.COMPLETED
    assert dag.is_terminal() is True

    n2.state = NodeState.FAILED
    assert dag.is_terminal() is True


def test_dag_find_upstream():
    n1 = DAGNode(node_id="n1", agent_type="A", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="B", input_query={}, depends_on=["n1"])
    n3 = DAGNode(node_id="n3", agent_type="C", input_query={}, depends_on=["n2"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2, n3])

    affected = dag.trace_upstream("n3")
    assert "n1" in affected
    assert "n2" in affected
    assert "n3" not in affected  # only upstream, not self
