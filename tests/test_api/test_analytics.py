"""Tests for the analytics endpoint and helper functions."""
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.analytics_builder import (
    build_scoring_data as _build_scoring_data,
    build_feature_data as _build_feature_data,
    build_sentiment_data as _build_sentiment_data,
    build_pricing_data as _build_pricing_data,
    build_swot_data as _build_swot_data,
    build_techstack_data as _build_techstack_data,
    extract_metadata as _extract_metadata,
    belongs_to_task as _belongs_to_task,
    normalize_product_name as _normalize_product_name,
)
from src.dag.models import TaskDAG
from src.knowledge_graph.models import (
    FeatureNode, PricingModelNode, ReportSectionNode, SentimentNode,
)
from src.knowledge_graph.store import GraphStore

client = TestClient(app)


# ── helper unit tests ──

def test_normalize_product_name():
    assert _normalize_product_name("notion") == "Notion"
    assert _normalize_product_name("Notion") == "Notion"
    assert _normalize_product_name("Notion ") == "Notion"
    assert _normalize_product_name(" slack ") == "Slack"
    assert _normalize_product_name("ChatGPT") == "ChatGPT"
    assert _normalize_product_name("") == "Unknown"

class FakeNode:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_scoring_node(product, dimension, score, weight=1.0, task_id="t1"):
    return FakeNode(
        product=product, dimension=dimension, score=score, weight=weight,
        metadata={"task_id": task_id},
    )


def test_build_scoring_data_empty():
    assert _build_scoring_data([]) == []


def test_build_scoring_data_normal():
    nodes = [
        make_scoring_node("Slack", "Features", 8.5),
        make_scoring_node("Slack", "Pricing", 6.2),
        make_scoring_node("Teams", "Features", 7.0),
        make_scoring_node("Teams", "Pricing", 8.0),
    ]
    result = _build_scoring_data(nodes)
    assert len(result) == 4
    assert result[0] == {"product": "Slack", "dimension": "Features", "score": 8.5, "weight": 1.0}


def test_build_feature_data_empty():
    assert _build_feature_data([]) == {"products": [], "features": []}


def test_build_feature_data_merges_same_feature():
    nodes = [
        FakeNode(product="Slack", feature_name="SSO", category="Security",
                  maturity="ga", differentiation="advantage", metadata={"task_id": "t1"}),
        FakeNode(product="Teams", feature_name="SSO", category="Security",
                  maturity="beta", differentiation="parity", metadata={"task_id": "t1"}),
    ]
    result = _build_feature_data(nodes)
    assert len(result["features"]) == 1
    f = result["features"][0]
    assert f["feature_name"] == "SSO"
    assert f["Slack_maturity"] == "ga"
    assert f["Teams_maturity"] == "beta"


def test_build_sentiment_data_empty():
    assert _build_sentiment_data([]) == {"products": [], "topics": []}


def test_build_sentiment_data_normal():
    nodes = [
        FakeNode(product="Slack", topic="Ease of Use", sentiment_score=0.7,
                  trend="rising", metadata={"task_id": "t1"}),
        FakeNode(product="Slack", topic="Support", sentiment_score=-0.3,
                  trend="declining", metadata={"task_id": "t1"}),
    ]
    result = _build_sentiment_data(nodes)
    assert len(result["topics"]) == 2
    assert result["topics"][0]["Slack_score"] == 0.7


def test_build_pricing_data():
    pnodes = [
        FakeNode(product="Slack", plan_name="Pro", price=12.99, billing_cycle="monthly", metadata={}),
        FakeNode(product="Teams", plan_name="Free", price=0, billing_cycle="monthly", metadata={}),
    ]
    mnodes = [
        FakeNode(product="Slack", value_score=0.82, strategy="freemium",
                  target_segment="SMB", metadata={}),
    ]
    result = _build_pricing_data(pnodes, mnodes)
    assert len(result["plans"]) == 2
    assert result["plans"][0]["price"] == 12.99
    assert len(result["value_scores"]) == 1
    assert result["value_scores"][0]["value_score"] == 0.82


def test_build_swot_data():
    nodes = [
        FakeNode(product="Slack", strengths=["a", "b"], weaknesses=["c"],
                  opportunities=["d", "e", "f"], threats=[], metadata={}),
    ]
    result = _build_swot_data(nodes)
    assert result[0]["strengths_count"] == 2
    assert result[0]["weaknesses_count"] == 1
    assert result[0]["opportunities_count"] == 3
    assert result[0]["threats_count"] == 0


def test_build_techstack_data():
    nodes = [
        FakeNode(product="Slack", languages=["Python", "JS"], frameworks=["React"],
                  infra=["AWS"], metadata={}),
    ]
    result = _build_techstack_data(nodes)
    assert len(result["languages"]) == 2
    assert result["languages"][0] == {"name": "Python", "Slack": True}


def test_belongs_to_task_by_metadata():
    node = FakeNode(product="", metadata={"task_id": "t1"})
    assert _belongs_to_task(node, "t1", []) is True
    assert _belongs_to_task(node, "t2", []) is False


def test_belongs_to_task_ignores_product_fallback():
    node = FakeNode(product="Slack", metadata={})
    assert _belongs_to_task(node, "t1", ["Slack", "Teams"]) is False
    assert _belongs_to_task(node, "t1", ["Discord"]) is False


class FakeScheduler:
    def __init__(self, targets=None):
        self.targets = targets or []

    def get_task_dag(self, task_id):
        return TaskDAG(task_id=task_id, targets=self.targets)


def test_analytics_uses_only_current_task_structured_nodes(tmp_path):
    """同名产品的历史节点不能混入当前任务图表。"""
    from src.api.analytics_builder import build_analytics_payload

    store = GraphStore(db_path=str(tmp_path / "kg.db"))
    store.create_node(FeatureNode(
        product="Figma", name="Old Feature", category="UI",
        maturity="ga", differentiation="advantage",
        metadata={"task_id": "old_task"},
    ))
    store.create_node(FeatureNode(
        product="Figma", name="Current Feature", category="UI",
        maturity="ga", differentiation="advantage",
        metadata={"task_id": "current_task"},
    ))
    store.create_node(PricingModelNode(
        product="Figma", strategy="per-seat", target_segment="teams",
        value_score=0.9, metadata={"task_id": "old_task"},
    ))
    store.create_node(PricingModelNode(
        product="Figma", strategy="per-seat", target_segment="teams",
        value_score=0.7, metadata={"task_id": "current_task"},
    ))

    payload = build_analytics_payload(store, FakeScheduler(["Figma"]), "current_task")

    features = payload["features"]["features"]
    assert len(features) == 1
    assert features[0]["feature_name"] == "Current Feature"
    assert payload["pricing"]["value_scores"] == [{
        "product": "Figma",
        "value_score": 0.7,
        "strategy": "per-seat",
        "target_segment": "teams",
    }]
    assert payload["data_source"] == "structured"


def test_analytics_builds_fallback_from_current_report_section(tmp_path):
    """没有结构化节点时，从当前任务报告正文解析出图表兜底数据。"""
    from src.api.analytics_builder import build_analytics_payload

    store = GraphStore(db_path=str(tmp_path / "kg.db"))
    store.create_node(ReportSectionNode(
        section="完整报告",
        order=0,
        metadata={"task_id": "report_task"},
        content=(
            "# Competitive Analysis of Notion, Figma, Sketch\n\n"
            "## Feature Analysis\n\n"
            "| Feature | Notion | Figma | Sketch |\n"
            "|---------|--------|-------|--------|\n"
            "| Documentation | Advantage | Disadvantage | Disadvantage |\n"
            "| Real-time Collaboration | Parity | Advantage | Disadvantage |\n\n"
            "## Pricing Analysis\n\n"
            "| Plan | Notion | Figma | Sketch |\n"
            "|------|--------|-------|--------|\n"
            "| Free | Free | Free | N/A |\n"
            "| Pro | $10/mo | $12/editor/mo | $99/year |\n\n"
            "## Sentiment Analysis\n\n"
            "Figma overall sentiment score 0.6. Notion sentiment score 0.7.\n\n"
            "## SWOT Analysis\n\n"
            "### Notion\n"
            "**Strengths:** Flexible, strong community.\n"
            "**Weaknesses:** Performance issues.\n"
            "**Opportunities:** AI features.\n"
            "**Threats:** Microsoft Loop.\n\n"
            "### Figma\n"
            "**Strengths:** Real-time collaboration.\n"
            "**Weaknesses:** Limited offline.\n"
            "**Opportunities:** AI design.\n"
            "**Threats:** Penpot.\n"
        ),
    ))

    payload = build_analytics_payload(
        store, FakeScheduler(["Notion", "Figma", "Sketch"]), "report_task"
    )

    assert payload["data_source"] == "report_fallback"
    assert payload["warnings"]
    assert payload["features"]["features"][0]["feature_name"] == "Documentation"
    assert len(payload["pricing"]["plans"]) == 5
    assert {row["product"] for row in payload["pricing"]["plans"]} == {"Notion", "Figma", "Sketch"}
    assert len(payload["swot"]) == 2
    assert payload["scoring"]


def test_analytics_derives_scoring_when_scoring_nodes_missing(tmp_path):
    """当前任务没有 ScoringNode 时，也能从结构化节点派生雷达评分。"""
    from src.api.analytics_builder import build_analytics_payload

    store = GraphStore(db_path=str(tmp_path / "kg.db"))
    store.create_node(FeatureNode(
        product="Notion", name="Docs", category="UI",
        maturity="ga", differentiation="advantage",
        metadata={"task_id": "score_task"},
    ))
    store.create_node(PricingModelNode(
        product="Notion", strategy="freemium", target_segment="teams",
        value_score=0.72, metadata={"task_id": "score_task"},
    ))
    store.create_node(SentimentNode(
        product="Notion", topic="overall", sentiment_score=0.6,
        metadata={"task_id": "score_task"},
    ))

    payload = build_analytics_payload(store, FakeScheduler(["Notion"]), "score_task")

    dimensions = {row["dimension"] for row in payload["scoring"]}
    assert {"features", "pricing", "sentiment"}.issubset(dimensions)
    assert all(row["product"] == "Notion" for row in payload["scoring"])


# ── endpoint integration tests ──

def test_analytics_endpoint_returns_200():
    resp = client.get("/api/report/test_task_1/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert "products" in data
    assert "scoring" in data
    assert "features" in data
    assert "sentiment" in data
    assert "pricing" in data
    assert "swot" in data
    assert "tech_stack" in data


def test_analytics_endpoint_empty_when_no_data():
    """Analytics endpoint returns empty containers, not errors, for missing data."""
    resp = client.get("/api/report/nonexistent_task_xyz/analytics")
    assert resp.status_code == 200
    data = resp.json()
    # all containers should be empty
    assert data["scoring"] == []
    assert data["features"] == {"products": [], "features": []}
    assert data["swot"] == []
    assert data["pricing"]["plans"] == []
