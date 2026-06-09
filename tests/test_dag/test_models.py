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
    n1 = DAGNode(node_id="collector", agent_type="Collector", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="feature_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n3 = DAGNode(node_id="pricing_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n1.state = NodeState.COMPLETED

    dag = TaskDAG(task_id="task_1", nodes=[n1, n2, n3])
    ready = dag.get_ready_nodes()
    assert len(ready) == 2
    assert {n.node_id for n in ready} == {"feature_analysis", "pricing_analysis"}


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


def test_dag_node_platform_metadata_defaults():
    node = DAGNode(
        node_id="feature_analysis",
        agent_type="Analyst",
        input_query={"targets": ["Notion", "ClickUp"]},
    )

    assert node.stage == ""
    assert node.role_group == ""
    assert node.display_name == ""
    assert node.description == ""
    assert node.output_contract == ""
    assert node.degradation_policy == {}
    assert node.source_policy == {}


def test_task_dag_platform_metadata_and_stage_lookup():
    n1 = DAGNode(
        node_id="collector",
        agent_type="Collector",
        input_query={},
        stage="collection",
        role_group="research",
    )
    n2 = DAGNode(
        node_id="feature_analysis",
        agent_type="Analyst",
        input_query={},
        depends_on=["collector"],
        stage="analysis",
        role_group="analysis",
    )
    dag = TaskDAG(
        task_id="task_template",
        nodes=[n1, n2],
        workflow_template_id="saas_competitor_analysis",
        scenario="saas",
        targets=["Notion", "ClickUp"],
        metadata={"planning_mode": "template"},
    )

    assert dag.workflow_template_id == "saas_competitor_analysis"
    assert dag.scenario == "saas"
    assert dag.targets == ["Notion", "ClickUp"]
    assert dag.metadata["planning_mode"] == "template"
    assert dag.get_nodes_by_stage("analysis") == [n2]


def test_new_feedback_states_are_non_terminal_until_resolved():
    n1 = DAGNode(node_id="n1", agent_type="QA", input_query={})
    n2 = DAGNode(node_id="n2", agent_type="ReportGenerator", input_query={})
    dag = TaskDAG(task_id="task_feedback", nodes=[n1, n2])

    n1.state = NodeState.REJECTED
    n2.state = NodeState.RERUNNING

    assert dag.is_terminal() is False
