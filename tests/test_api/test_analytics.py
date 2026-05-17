"""Tests for the analytics endpoint and helper functions."""
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.routes.report import (
    _build_scoring_data, _build_feature_data, _build_sentiment_data,
    _build_pricing_data, _build_swot_data, _build_techstack_data,
    _extract_metadata, _belongs_to_task,
)

client = TestClient(app)


# ── helper unit tests ──

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


def test_belongs_to_task_by_product():
    node = FakeNode(product="Slack", metadata={})
    assert _belongs_to_task(node, "t1", ["Slack", "Teams"]) is True
    assert _belongs_to_task(node, "t1", ["Discord"]) is False


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
