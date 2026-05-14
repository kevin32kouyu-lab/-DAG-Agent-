import pytest
from datetime import datetime
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, FeatureNode, FeatureMatrixNode,
    SWOTNode, ScoringNode, InsightNode, GraphEdge, EdgeType,
)


def test_source_info_node_defaults():
    node = SourceInfoNode(
        url="https://g2.com/products/notion/reviews",
        domain="g2.com",
        credibility_score=0.85,
    )
    assert node.node_type == "SourceInfo"
    assert node.layer == 1
    assert node.credibility_score == 0.85
    assert node.id.startswith("node_")


def test_feature_node_required_fields():
    node = FeatureNode(product="Notion", name="AI Writer", category="AI Features")
    assert node.node_type == "FeatureNode"
    assert node.layer == 2
    assert node.maturity == "unknown"
    assert node.differentiation == "parity"


def test_graph_edge_type_enum():
    edge = GraphEdge(
        source_id="node_a", target_id="node_b",
        edge_type=EdgeType.DERIVED_FROM,
    )
    assert edge.edge_type == "derived_from"
    assert edge.id.startswith("edge_")


def test_feature_matrix_structure():
    matrix = FeatureMatrixNode(
        products=["Notion", "Linear"],
        dimensions=["ai", "docs"],
        matrix={
            "Notion": {"ai": "★★★★★", "docs": "★★★★"},
            "Linear": {"ai": "★★", "docs": "★★★"},
        },
    )
    assert matrix.node_type == "FeatureMatrix"
    assert matrix.matrix["Notion"]["ai"] == "★★★★★"


def test_swot_node_lists():
    node = SWOTNode(
        product="Notion",
        strengths=["All-in-one", "AI features"],
        weaknesses=["Performance"],
        opportunities=["Enterprise"],
        threats=["Microsoft Loop"],
    )
    assert len(node.strengths) == 2
    assert node.layer == 3
