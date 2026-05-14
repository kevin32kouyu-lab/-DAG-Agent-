import pytest
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler


def build_test_dag():
    """Build DAG: sd → col → feat/sent → swot → writer → qa"""
    n_sd = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n_col = DAGNode(node_id="col", agent_type="Collector", input_query={}, depends_on=["sd"])
    n_feat = DAGNode(node_id="feat", agent_type="FeatureAnalyzer", input_query={}, depends_on=["col"])
    n_sent = DAGNode(node_id="sent", agent_type="SentimentAnalyzer", input_query={}, depends_on=["col"])
    n_swot = DAGNode(node_id="swot", agent_type="SWOTAnalyzer", input_query={}, depends_on=["feat", "sent"])
    n_writer = DAGNode(node_id="writer", agent_type="Writer", input_query={}, depends_on=["swot"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])
    for n in [n_sd, n_col, n_feat, n_sent, n_swot, n_writer]:
        n.state = NodeState.COMPLETED
    n_qa.state = NodeState.PENDING
    return TaskDAG(task_id="fb_test", nodes=[n_sd, n_col, n_feat, n_sent, n_swot, n_writer, n_qa])


class TestFeedbackQARejection:
    def test_resets_upstream_and_downstream_of_failed_node(self):
        """When feat fails QA, reset feat + its upstream (col, sd) + downstream (swot, writer)."""
        dag = build_test_dag()
        handler = FeedbackHandler()

        affected = handler.handle_qa_rejection(
            dag, qa_node_id="qa1",
            failed_nodes=["feat"],
            reasons=["FeatureMatrix uses outdated data"],
            qa_round=1,
        )

        # Upstream: col and sd feed into feat
        assert "feat" in affected
        assert "col" in affected
        assert "sd" in affected
        # Downstream: swot and writer consumed feat's stale output
        assert "swot" in affected
        assert "writer" in affected
        # Independent branch: sentiment is parallel to feat
        assert "sent" not in affected

        # Verify nodes actually reset
        assert dag.get_node("feat").state == NodeState.PENDING
        assert dag.get_node("swot").state == NodeState.PENDING
        assert dag.get_node("sent").state == NodeState.COMPLETED

    def test_max_two_rounds_then_degraded(self):
        dag = build_test_dag()
        handler = FeedbackHandler()

        # Round 1: should work
        affected1 = handler.handle_qa_rejection(dag, "qa1", ["feat"], ["stale data"], qa_round=1)
        assert len(affected1) > 0
        assert dag.get_node("qa1").qa_round == 1

        # Reset back for next round
        for nid in ["feat", "col", "sd", "swot", "writer"]:
            dag.get_node(nid).state = NodeState.COMPLETED

        # Round 2: should still work
        affected2 = handler.handle_qa_rejection(dag, "qa1", ["feat"], ["still broken"], qa_round=2)
        assert "feat" in affected2

        # Reset back
        for nid in ["feat", "col", "sd", "swot", "writer"]:
            dag.get_node(nid).state = NodeState.COMPLETED

        # Round 3: should NOT reset, mark QA as DEGRADED
        affected3 = handler.handle_qa_rejection(dag, "qa1", ["feat"], ["persistent"], qa_round=3)
        assert len(affected3) == 0
        qa_node = dag.get_node("qa1")
        assert qa_node.state == NodeState.DEGRADED
        assert "qa_notes" in qa_node.context


class TestFeedbackCrossReviewRejection:
    def test_high_severity_triggers_reset(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "conflict", "severity": "high",
             "involved_agents": ["FeatureAnalyzer", "SentimentAnalyzer"],
             "description": "Docs feature score contradicts user sentiment"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        # feat and sent both involved → their upstream (col, sd) should be reset
        assert "feat" in affected
        assert "sent" in affected
        assert "col" in affected

    def test_low_severity_no_reset(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "confidence_anomaly", "severity": "low",
             "involved_agents": ["TechStackAnalyzer"],
             "description": "High confidence with few sources"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        assert len(affected) == 0

    def test_medium_omission_triggers_incremental_supplement(self):
        """Medium severity omission: reset only target agent, not upstream."""
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "omission", "severity": "medium",
             "source_agent": "SentimentAnalyzer",
             "target_agent": "FeatureAnalyzer",
             "detail": "G2 reviews mention API integration, feature analysis missed it"},
        ]
        affected = handler.handle_cross_review_rejection(dag, flags)
        # Target agent (feat) should be reset
        assert "feat" in affected
        # Upstream (col, sd) should NOT be reset for medium omission
        assert "col" not in affected
        assert "sd" not in affected
        # Target agent should have omission context injected
        feat_node = dag.get_node("feat")
        assert feat_node.state == NodeState.PENDING
        assert "omission_context" in feat_node.context
        omitted_detail = feat_node.context["omission_context"][0]
        assert omitted_detail["flag_type"] == "omission"

    def test_medium_low_severity_no_cross_review_retry_count(self):
        """Medium/low severity should not consume cross_review_retries counter."""
        dag = build_test_dag()
        handler = FeedbackHandler()
        for n in dag.nodes:
            if n.agent_type == "FeatureAnalyzer":
                n.state = NodeState.COMPLETED
        flags = [
            {"flag_type": "omission", "severity": "medium",
             "source_agent": "SentimentAnalyzer",
             "target_agent": "FeatureAnalyzer",
             "detail": "API integration not covered"},
        ]
        handler.handle_cross_review_rejection(dag, flags)
        feat_node = dag.get_node("feat")
        # cross_review_retries should NOT increment for medium severity
        assert feat_node.cross_review_retries == 0

    def test_cross_review_max_one_round(self):
        dag = build_test_dag()
        handler = FeedbackHandler()
        flags = [
            {"flag_type": "conflict", "severity": "high",
             "involved_agents": ["FeatureAnalyzer"],
             "description": "Conflict detected"},
        ]

        # Round 1: works
        affected1 = handler.handle_cross_review_rejection(dag, flags)
        assert "feat" in affected1

        # Reset back
        for nid in affected1:
            dag.get_node(nid).state = NodeState.COMPLETED

        # Round 2: should NOT reset (max 1 round for cross-review)
        affected2 = handler.handle_cross_review_rejection(dag, flags)
        assert len(affected2) == 0
