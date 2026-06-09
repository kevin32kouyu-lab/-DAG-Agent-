import pytest
from unittest.mock import MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler


def build_test_dag():
    """Build DAG: collector → feat/sent → cross_review → writer → qa
    用新 agent_type 构造 8 节点 DAG 的子集。"""
    n_col = DAGNode(node_id="collector", agent_type="Collector", input_query={}, depends_on=[])
    n_feat = DAGNode(node_id="feature_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n_sent = DAGNode(node_id="sentiment_analysis", agent_type="Analyst", input_query={}, depends_on=["collector"])
    n_cr = DAGNode(node_id="cross_review", agent_type="Analyst", input_query={}, depends_on=["feature_analysis", "sentiment_analysis"])
    n_writer = DAGNode(node_id="report", agent_type="ReportGenerator", input_query={}, depends_on=["cross_review"])
    n_qa = DAGNode(node_id="qa", agent_type="QA", input_query={}, depends_on=["report"])
    for n in [n_col, n_feat, n_sent, n_cr, n_writer]:
        n.state = NodeState.COMPLETED
    n_qa.state = NodeState.PENDING
    return TaskDAG(task_id="fb_test", nodes=[n_col, n_feat, n_sent, n_cr, n_writer, n_qa])


class TestFeedbackQARejection:
    def test_resets_only_report_and_qa_nodes(self):
        """When QA fails, only reset Writer and QA nodes, not the entire upstream chain."""
        dag = build_test_dag()
        handler = FeedbackHandler()

        affected = handler.handle_qa_rejection(
            dag, qa_node_id="qa",
            failed_nodes=["feature_analysis"],
            reasons=["FeatureMatrix uses outdated data"],
            qa_round=1,
        )

        # Only report and qa should be reset
        assert "report" in affected
        assert "qa" in affected
        # Upstream analysis nodes should NOT be reset
        assert "feature_analysis" not in affected
        assert "collector" not in affected
        assert "cross_review" not in affected
        assert "sentiment_analysis" not in affected

        # Verify nodes actually reset
        assert dag.get_node("report").state == NodeState.PENDING
        assert dag.get_node("qa").state == NodeState.PENDING
        # Other nodes should remain completed
        assert dag.get_node("feature_analysis").state == NodeState.COMPLETED
        assert dag.get_node("sentiment_analysis").state == NodeState.COMPLETED

    def test_max_one_round_then_degraded(self):
        dag = build_test_dag()
        handler = FeedbackHandler()

        # Round 1: should work
        affected1 = handler.handle_qa_rejection(dag, "qa", ["feature_analysis"], ["stale data"], qa_round=1)
        assert len(affected1) > 0
        assert dag.get_node("qa").qa_round == 1

        # Reset back for next round
        for nid in ["report", "qa"]:
            dag.get_node(nid).state = NodeState.COMPLETED

        # Round 2: should NOT reset, mark QA as DEGRADED (max 1 round)
        affected2 = handler.handle_qa_rejection(dag, "qa", ["feature_analysis"], ["still broken"], qa_round=2)
        assert len(affected2) == 0
        qa_node = dag.get_node("qa")
        assert qa_node.state == NodeState.DEGRADED
        assert "qa_notes" in qa_node.context


class TestFeedbackCrossReviewRejection:
    def test_high_severity_triggers_reset(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "conflict", "severity": "high",
             "involved_node_ids": ["feature_analysis", "sentiment_analysis"],
             "description": "Feature score contradicts user sentiment"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        # Only the involved nodes should be reset, NOT the upstream collector
        assert "feature_analysis" in affected
        assert "sentiment_analysis" in affected
        assert "collector" not in affected

    def test_low_severity_no_reset(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "confidence_anomaly", "severity": "low",
             "involved_node_ids": ["feature_analysis"],
             "description": "High confidence with few sources"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        assert len(affected) == 0

    def test_medium_omission_triggers_incremental_supplement(self):
        """Medium severity omission: reset only target node, not upstream."""
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "omission", "severity": "medium",
             "target_node_id": "feature_analysis",
             "detail": "G2 reviews mention API integration, feature analysis missed it"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        # Target node (feature_analysis) should be reset
        assert "feature_analysis" in affected
        # Upstream (collector) should NOT be reset for medium omission
        assert "collector" not in affected
        # Target node should have omission context injected
        feat_node = dag.get_node("feature_analysis")
        assert feat_node.state == NodeState.PENDING
        assert "omission_context" in feat_node.context
        omitted_detail = feat_node.context["omission_context"][0]
        assert omitted_detail["flag_type"] == "omission"

    def test_medium_low_severity_no_cross_review_retry_count(self):
        """Medium/low severity should not consume cross_review_retries counter."""
        dag = build_test_dag()
        handler = FeedbackHandler()
        for n in dag.nodes:
            if n.node_id == "feature_analysis":
                n.state = NodeState.COMPLETED
        flags = [
            {"flag_type": "omission", "severity": "medium",
             "target_node_id": "feature_analysis",
             "detail": "API integration not covered"},
        ]
        handler.handle_cross_review_rejection(dag, flags)
        feat_node = dag.get_node("feature_analysis")
        # cross_review_retries should NOT increment for medium severity
        assert feat_node.cross_review_retries == 0

    def test_cross_review_max_one_round(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "conflict", "severity": "high",
             "involved_node_ids": ["feature_analysis"],
             "description": "Conflict detected"},
        ]

        # Round 1: works
        affected1 = handler.handle_cross_review_rejection(dag, flags)
        assert "feature_analysis" in affected1

        # Reset back
        for nid in affected1:
            dag.get_node(nid).state = NodeState.COMPLETED

        # Round 2: should DEGRADE (max 1 round for cross-review exceeded)
        affected2 = handler.handle_cross_review_rejection(dag, flags)
        assert "feature_analysis" in affected2
        feat_node = dag.get_node("feature_analysis")
        assert feat_node.state == NodeState.DEGRADED
        assert feat_node.cross_review_retries == 1  # unchanged, capped


def test_feedback_audit_failure_is_logged(caplog):
    dag = build_test_dag()
    audit_logger = MagicMock()
    audit_logger.log_event.side_effect = RuntimeError("audit unavailable")
    handler = FeedbackHandler(audit_logger=audit_logger)
    flags = [
        {"flag_type": "conflict", "severity": "high",
         "involved_node_ids": ["feature_analysis"],
         "description": "Conflict detected"},
    ]

    caplog.set_level("WARNING", logger="src.dag.feedback")

    affected = handler.handle_cross_review_rejection(dag, flags)

    assert "feature_analysis" in affected
    assert "反馈审计写入失败" in caplog.text
    assert "audit unavailable" in caplog.text
