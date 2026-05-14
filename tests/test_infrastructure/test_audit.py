import pytest
from src.infrastructure.audit import AuditLogger
from src.agents.base import StepTrace


@pytest.fixture
def audit():
    return AuditLogger(":memory:")


def test_log_event_creates_entry(audit):
    audit.log_event("task1", "node1", "TestAgent", "node_started", {"detail": "ok"})
    logs = audit.get_task_log("task1")
    assert len(logs) == 1
    assert logs[0]["task_id"] == "task1"
    assert logs[0]["node_id"] == "node1"
    assert logs[0]["agent_type"] == "TestAgent"
    assert logs[0]["event"] == "node_started"
    assert '"detail": "ok"' in logs[0]["data"]


def test_log_event_multiple_entries(audit):
    audit.log_event("task1", "node1", "AgentA", "start")
    audit.log_event("task1", "node2", "AgentB", "start")
    audit.log_event("task1", "node1", "AgentA", "complete")
    logs = audit.get_task_log("task1")
    assert len(logs) == 3


def test_get_task_log_filters_by_task_id(audit):
    audit.log_event("task1", "node1", "AgentA", "start")
    audit.log_event("task2", "node1", "AgentA", "start")
    assert len(audit.get_task_log("task1")) == 1
    assert len(audit.get_task_log("task2")) == 1
    assert len(audit.get_task_log("task3")) == 0


def test_log_step_trace_stores_trace(audit):
    trace = StepTrace(
        task_id="task1", node_id="node1", agent_type="TestAgent",
        step_number=0, observation_summary="observed data",
        reasoning="thought about it", action="web_search",
        action_params={"query": "test"}, action_result_summary="found results",
        llm_tokens=500, llm_cost=0.01,
        nodes_created=["n1"], edges_created=["e1"],
    )
    audit.log_step_trace(trace)
    traces = audit.get_step_traces("task1", "node1")
    assert len(traces) == 1
    assert traces[0]["task_id"] == "task1"
    assert traces[0]["node_id"] == "node1"
    assert traces[0]["step_number"] == 0
    assert traces[0]["reasoning"] == "thought about it"


def test_get_step_traces_filters_by_node_id(audit):
    t1 = StepTrace(task_id="task1", node_id="node_a", agent_type="A", step_number=0)
    t2 = StepTrace(task_id="task1", node_id="node_b", agent_type="B", step_number=0)
    audit.log_step_trace(t1)
    audit.log_step_trace(t2)
    assert len(audit.get_step_traces("task1", "node_a")) == 1
    assert len(audit.get_step_traces("task1", "node_b")) == 1
    assert len(audit.get_step_traces("task1", "node_c")) == 0


def test_get_step_traces_ordered_by_step(audit):
    for i in range(3):
        audit.log_step_trace(StepTrace(task_id="t1", node_id="n1", agent_type="A", step_number=i))
    traces = audit.get_step_traces("t1", "n1")
    steps = [t["step_number"] for t in traces]
    assert steps == [0, 1, 2]


def test_log_event_default_data(audit):
    audit.log_event("task1", "node1", "Test", "event_without_data")
    logs = audit.get_task_log("task1")
    assert logs[0]["data"] == "{}"


def test_source_degraded_audit_event(audit):
    audit.log_event("task1", "collector_1", "Collector", "source_degraded", {
        "source": "G2", "tier": 1, "reason": "HTTP 403",
        "fallback_used": "公开评分摘要"
    })
    logs = audit.get_task_log("task1")
    assert len(logs) == 1
    assert logs[0]["event"] == "source_degraded"
    assert "G2" in logs[0]["data"]
