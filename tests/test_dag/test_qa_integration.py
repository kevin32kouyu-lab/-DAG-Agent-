import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler
from src.dag.scheduler import DAGScheduler


def build_qa_dag():
    """Build DAG: collector → feature_analysis → report → qa
    用新 agent_type 构造。"""
    n_col = DAGNode(node_id="collector", agent_type="Collector", input_query={}, depends_on=[])
    n_feat = DAGNode(node_id="feature_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n_writer = DAGNode(node_id="report", agent_type="ReportGenerator", input_query={}, depends_on=["feature_analysis"])
    n_qa = DAGNode(node_id="qa", agent_type="QA", input_query={}, depends_on=["report"])
    return TaskDAG(task_id="qa_integration_test", nodes=[
        n_col, n_feat, n_writer, n_qa,
    ])


@pytest.mark.asyncio
async def test_qa_feedback_cycle_unit():
    """Unit test: DAG runs -> QA fails -> feedback resets Writer+QA -> re-runs -> QA passes"""
    dag = build_qa_dag()

    # Initial: all pre-QA nodes completed
    for n in dag.nodes:
        if n.agent_type != "QA":
            n.state = NodeState.COMPLETED

    handler = FeedbackHandler()

    # Round 1: QA fails on feature_analysis
    affected = handler.handle_qa_rejection(
        dag, qa_node_id="qa",
        failed_nodes=["feature_analysis"],
        reasons=["FeatureMatrix uses outdated webpage"],
        qa_round=1,
    )
    # Only report and qa should be affected (not upstream analysis nodes)
    assert "report" in affected
    assert "qa" in affected
    assert dag.get_node("report").state == NodeState.PENDING
    assert dag.get_node("qa").state == NodeState.PENDING
    # Upstream nodes should remain completed
    assert dag.get_node("feature_analysis").state == NodeState.COMPLETED
    assert dag.get_node("collector").state == NodeState.COMPLETED
    assert dag.get_node("qa").qa_round == 1

    # Re-run affected nodes (simulate executor)
    for nid in ["report", "qa"]:
        dag.get_node(nid).state = NodeState.COMPLETED

    # Round 2: QA passes (no failed nodes)
    affected2 = handler.handle_qa_rejection(
        dag, qa_node_id="qa",
        failed_nodes=[],
        reasons=[],
        qa_round=2,
    )
    assert len(affected2) == 0


@pytest.mark.asyncio
async def test_qa_max_rounds_then_degraded():
    """QA exceeds MAX_QA_ROUNDS -> DEGRADED state, no further resets"""
    dag = build_qa_dag()
    for n in dag.nodes:
        if n.agent_type != "QA":
            n.state = NodeState.COMPLETED

    handler = FeedbackHandler()

    # Round 1: works
    handler.handle_qa_rejection(dag, "qa", ["feature_analysis"], ["stale data"], qa_round=1)
    for nid in ["report", "qa"]:
        dag.get_node(nid).state = NodeState.COMPLETED

    # Round 2: DEGRADED (max 1 round)
    affected2 = handler.handle_qa_rejection(dag, "qa", ["feature_analysis"], ["still broken"], qa_round=2)
    assert len(affected2) == 0
    qa_node = dag.get_node("qa")
    assert qa_node.state == NodeState.DEGRADED
    assert "qa_notes" in qa_node.context


@pytest.mark.asyncio
async def test_qa_feedback_scheduler_integration():
    """Full integration: scheduler detects QA failures and triggers feedback loop."""
    dag = build_qa_dag()

    # Track which nodes the executor ran
    run_log = []
    qa_run_count = [0]

    async def mock_execute(node):
        run_log.append(node.node_id)
        if node.agent_type == "QA":
            qa_run_count[0] += 1
            if qa_run_count[0] == 1:
                # First QA run: simulate finding failed nodes via overall_pass=False
                node.context["_output_data"] = {
                    "overall_pass": False,
                    "fact_issues": [{"node_id": "feature_analysis", "reason": "Missing source", "severity": "high"}],
                    "logic_issues": [],
                    "rejection_reason": "Missing source for feature analysis",
                }
        node.state = NodeState.COMPLETED

    executor = MagicMock()
    executor.gateway = MagicMock()
    executor.gateway.cost_tracker = MagicMock()
    executor.gateway.cost_tracker.total_tokens = 0
    executor.gateway.cost_tracker.total_cost = 0.0
    executor.store = MagicMock()
    executor.store.query_nodes = MagicMock(return_value=[])
    executor.execute = AsyncMock(side_effect=mock_execute)

    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    # QA should have been called at least once
    assert qa_run_count[0] >= 1
    # feature_analysis should have been re-run due to feedback
    feat_runs = [n for n in run_log if n == "feature_analysis"]
    assert len(feat_runs) >= 1
    # All nodes should reach terminal state
    assert dag.get_node("collector").state == NodeState.COMPLETED
    assert dag.get_node("feature_analysis").state == NodeState.COMPLETED
    assert dag.get_node("report").state == NodeState.COMPLETED


@pytest.mark.asyncio
async def test_qa_feedback_cross_review_integration():
    """QA + CrossReview feedback in same DAG run."""
    dag = build_qa_dag()
    # Add a cross_review node
    n_cr = DAGNode(node_id="cross_review", agent_type="Analyst", input_query={}, depends_on=["feature_analysis"])
    n_writer = dag.get_node("report")
    n_writer.depends_on.append("cross_review")  # report now depends on cross-review too
    dag.nodes.append(n_cr)

    cr_run_count = [0]

    async def mock_execute(node):
        if node.node_id == "cross_review":
            cr_run_count[0] += 1
            if cr_run_count[0] == 1:
                node.context["_output_data"] = {
                    "flags": [
                        {"flag_type": "conflict", "severity": "high",
                         "involved_node_ids": ["feature_analysis"],
                         "description": "Feature scores conflict with pricing data"},
                    ]
                }
        if node.agent_type == "QA":
            node.context["_output_data"] = {"overall_pass": True, "fact_issues": [], "logic_issues": []}
        node.state = NodeState.COMPLETED

    executor = MagicMock()
    executor.gateway = MagicMock()
    executor.gateway.cost_tracker = MagicMock()
    executor.gateway.cost_tracker.total_tokens = 0
    executor.gateway.cost_tracker.total_cost = 0.0
    executor.store = MagicMock()
    executor.store.query_nodes = MagicMock(return_value=[])
    executor.execute = AsyncMock(side_effect=mock_execute)

    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    # CrossReview should have been triggered
    assert cr_run_count[0] >= 1
    # DAG should reach terminal state
    assert dag.is_terminal()


@pytest.mark.asyncio
async def test_independent_branch_not_affected():
    """QA failure should only reset Writer and QA nodes, not affect independent branches."""
    n_col = DAGNode(node_id="collector", agent_type="Collector", input_query={}, depends_on=[])
    n_feat = DAGNode(node_id="feature_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n_sent = DAGNode(node_id="sentiment_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n_writer = DAGNode(node_id="report", agent_type="ReportGenerator", input_query={}, depends_on=["feature_analysis", "sentiment_analysis"])
    n_qa = DAGNode(node_id="qa", agent_type="QA", input_query={}, depends_on=["report"])
    dag = TaskDAG(task_id="independent_test", nodes=[n_col, n_feat, n_sent, n_writer, n_qa])

    for n in [n_col, n_feat, n_sent, n_writer]:
        n.state = NodeState.COMPLETED

    handler = FeedbackHandler()
    affected = handler.handle_qa_rejection(
        dag, qa_node_id="qa",
        failed_nodes=["feature_analysis"],
        reasons=["stale data"],
        qa_round=1,
    )

    # Only report and qa should be affected
    assert "report" in affected
    assert "qa" in affected
    # All analysis nodes should remain completed
    assert "feature_analysis" not in affected
    assert "sentiment_analysis" not in affected
    assert "collector" not in affected
    assert dag.get_node("sentiment_analysis").state == NodeState.COMPLETED
    assert dag.get_node("feature_analysis").state == NodeState.COMPLETED
