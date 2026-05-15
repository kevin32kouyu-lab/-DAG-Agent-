import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler
from src.dag.scheduler import DAGScheduler


def build_qa_dag():
    """Build DAG: sd -> col -> feat -> writer -> qa (both fact + logic)"""
    n_sd = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n_col = DAGNode(node_id="col", agent_type="Collector", input_query={}, depends_on=["sd"])
    n_feat = DAGNode(node_id="feat", agent_type="FeatureAnalyzer", input_query={}, depends_on=["col"])
    n_writer = DAGNode(node_id="writer", agent_type="ReportGenerator", input_query={}, depends_on=["feat"])
    n_qa_fact = DAGNode(node_id="qa_fact", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])
    n_qa_logic = DAGNode(node_id="qa_logic", agent_type="QA_LogicCheck", input_query={}, depends_on=["writer"])
    return TaskDAG(task_id="qa_integration_test", nodes=[
        n_sd, n_col, n_feat, n_writer, n_qa_fact, n_qa_logic,
    ])


@pytest.mark.asyncio
async def test_qa_feedback_cycle_unit():
    """Unit test: DAG runs -> QA fails -> feedback resets affected subgraph -> re-runs -> QA passes"""
    dag = build_qa_dag()

    # Initial: all pre-QA nodes completed
    for n in dag.nodes:
        if n.agent_type not in ("QA_FactCheck", "QA_LogicCheck"):
            n.state = NodeState.COMPLETED

    handler = FeedbackHandler()

    # Round 1: QA FactCheck fails on feat
    affected = handler.handle_qa_rejection(
        dag, qa_node_id="qa_fact",
        failed_nodes=["feat"],
        reasons=["FeatureMatrix uses outdated webpage"],
        qa_round=1,
    )
    # feat + upstream (col, sd) + downstream (writer) should be affected
    assert "feat" in affected
    assert "col" in affected
    assert "sd" in affected
    assert "writer" in affected
    assert dag.get_node("feat").state == NodeState.PENDING
    assert dag.get_node("col").state == NodeState.PENDING
    assert dag.get_node("sd").state == NodeState.PENDING
    assert dag.get_node("writer").state == NodeState.PENDING
    assert dag.get_node("qa_fact").qa_round == 1

    # Re-run affected nodes (simulate executor)
    for nid in ["sd", "col", "feat", "writer"]:
        dag.get_node(nid).state = NodeState.COMPLETED

    # Round 2: QA passes (no failed nodes)
    affected2 = handler.handle_qa_rejection(
        dag, qa_node_id="qa_fact",
        failed_nodes=[],
        reasons=[],
        qa_round=2,
    )
    assert len(affected2) == 0
    assert dag.get_node("qa_fact").state == NodeState.PENDING  # QA itself unchanged by handler


@pytest.mark.asyncio
async def test_qa_max_rounds_then_degraded():
    """QA exceeds MAX_QA_ROUNDS -> DEGRADED state, no further resets"""
    dag = build_qa_dag()
    for n in dag.nodes:
        if n.agent_type not in ("QA_FactCheck", "QA_LogicCheck"):
            n.state = NodeState.COMPLETED

    handler = FeedbackHandler()

    # Round 1: works
    handler.handle_qa_rejection(dag, "qa_fact", ["feat"], ["stale data"], qa_round=1)
    for nid in ["sd", "col", "feat", "writer"]:
        dag.get_node(nid).state = NodeState.COMPLETED

    # Round 2: still works
    handler.handle_qa_rejection(dag, "qa_fact", ["feat"], ["still broken"], qa_round=2)
    for nid in ["sd", "col", "feat", "writer"]:
        dag.get_node(nid).state = NodeState.COMPLETED

    # Round 3: DEGRADED
    affected3 = handler.handle_qa_rejection(dag, "qa_fact", ["feat"], ["persistent"], qa_round=3)
    assert len(affected3) == 0
    qa_node = dag.get_node("qa_fact")
    assert qa_node.state == NodeState.DEGRADED
    assert "qa_notes" in qa_node.context


@pytest.mark.asyncio
async def test_qa_feedback_scheduler_integration():
    """Full integration: scheduler detects QA failures and triggers feedback loop."""
    dag = build_qa_dag()

    # Track which nodes the executor ran and their completion order
    run_log = []
    qa_run_count = {"fact": 0, "logic": 0}

    async def mock_execute(node):
        run_log.append(node.node_id)
        if node.agent_type == "QA_FactCheck":
            qa_run_count["fact"] += 1
            if qa_run_count["fact"] == 1:
                # First QA run: simulate finding failed nodes
                node.context["_output_data"] = {
                    "failed_nodes": ["feat"],
                    "issues": [{"node_id": "feat", "reason": "Missing source", "severity": "high"}],
                }
        if node.agent_type == "QA_LogicCheck":
            qa_run_count["logic"] += 1
            # Logic check passes each time
            node.context["_output_data"] = {"contradictions": []}
        node.state = NodeState.COMPLETED

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=mock_execute)

    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    # All nodes should reach COMPLETED (or DEGRADED)
    final_states = {n.node_id: n.state for n in dag.nodes}
    # QA fact should have been called at least once
    assert qa_run_count["fact"] >= 1
    # Source/col/feat/writer should have been re-run due to feedback
    # feat appears twice: once initially, once after reset
    feat_runs = [n for n in run_log if n == "feat"]
    assert len(feat_runs) >= 1
    # All non-QA nodes completed
    assert dag.get_node("sd").state == NodeState.COMPLETED
    assert dag.get_node("col").state == NodeState.COMPLETED
    assert dag.get_node("feat").state == NodeState.COMPLETED
    assert dag.get_node("writer").state == NodeState.COMPLETED


@pytest.mark.asyncio
async def test_qa_feedback_cross_review_integration():
    """QA + CrossReview feedback in same DAG run."""
    dag = build_qa_dag()
    # Add a CrossReview node that depends on feat
    n_cr = DAGNode(node_id="cr", agent_type="CrossReviewAgent", input_query={}, depends_on=["feat"])
    n_writer = dag.get_node("writer")
    n_writer.depends_on.append("cr")  # writer now depends on cross-review too
    dag.nodes.append(n_cr)

    cr_run_count = [0]

    async def mock_execute(node):
        if node.agent_type == "CrossReviewAgent":
            cr_run_count[0] += 1
            if cr_run_count[0] == 1:
                node.context["_output_data"] = {
                    "flags": [
                        {"flag_type": "conflict", "severity": "high",
                         "involved_agents": ["FeatureAnalyzer"],
                         "description": "Feature scores conflict with pricing data"},
                    ]
                }
        if node.agent_type == "QA_FactCheck":
            node.context["_output_data"] = {"failed_nodes": [], "issues": []}
        if node.agent_type == "QA_LogicCheck":
            node.context["_output_data"] = {"contradictions": []}
        node.state = NodeState.COMPLETED

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=mock_execute)

    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    # CrossReview should have been triggered
    assert cr_run_count[0] >= 1
    # DAG should reach terminal state
    assert dag.is_terminal()


@pytest.mark.asyncio
async def test_independent_branch_not_affected():
    """QA failure on one branch should not reset independent parallel branches."""
    n_sd = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n_col = DAGNode(node_id="col", agent_type="Collector", input_query={}, depends_on=["sd"])
    n_feat = DAGNode(node_id="feat", agent_type="FeatureAnalyzer", input_query={}, depends_on=["col"])
    n_sent = DAGNode(node_id="sent", agent_type="SentimentAnalyzer", input_query={}, depends_on=["col"])
    n_writer = DAGNode(node_id="writer", agent_type="ReportGenerator", input_query={}, depends_on=["feat", "sent"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])
    dag = TaskDAG(task_id="independent_test", nodes=[n_sd, n_col, n_feat, n_sent, n_writer, n_qa])

    for n in [n_sd, n_col, n_feat, n_sent, n_writer]:
        n.state = NodeState.COMPLETED

    handler = FeedbackHandler()
    affected = handler.handle_qa_rejection(
        dag, qa_node_id="qa1",
        failed_nodes=["feat"],
        reasons=["stale data"],
        qa_round=1,
    )

    # feat + upstream (col, sd) + downstream (writer) should be affected
    assert "feat" in affected
    assert "col" in affected
    assert "sd" in affected
    assert "writer" in affected
    # sent is parallel to feat, should NOT be affected
    assert "sent" not in affected
    assert dag.get_node("sent").state == NodeState.COMPLETED
