import pytest
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, FeatureNode, InsightNode,
    GraphEdge, EdgeType,
)
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.query import bfs_trace, find_contradictions, get_confidence_breakdown


@pytest.fixture
def populated_store(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    s = store.create_node(SourceInfoNode(url="https://g2.com", domain="g2.com", credibility_score=0.85))
    w = store.create_node(WebPageNode(url="https://g2.com/r", title="Reviews"))
    f = store.create_node(FeatureNode(product="Notion", name="AI", category="AI"))
    i = store.create_node(InsightNode(insight="Strong AI features", confidence=0.82))
    store.create_edge(GraphEdge(source_id=w.id, target_id=s.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=f.id, target_id=w.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=f.id, target_id=i.id, edge_type=EdgeType.SUPPORTS))
    return store, {"source": s, "webpage": w, "feature": f, "insight": i}


def test_bfs_trace_returns_chain(populated_store):
    store, nodes = populated_store
    chain = bfs_trace(store, nodes["insight"].id, max_depth=3)
    assert len(chain) >= 2
    assert chain[0]["depth"] == 0


def test_find_contradictions(populated_store):
    store, nodes = populated_store
    review = store.create_node(FeatureNode(product="Notion", name="neg1", category="f"))
    store.create_edge(GraphEdge(source_id=review.id, target_id=nodes["feature"].id, edge_type=EdgeType.CONTRADICTS))
    contradictions = find_contradictions(store, nodes["feature"].id)
    assert len(contradictions) == 1
    assert contradictions[0]["evidence"]["node_type"] == "FeatureNode"


def test_get_confidence_breakdown(populated_store):
    store, nodes = populated_store
    breakdown = get_confidence_breakdown(store, nodes["insight"].id)
    assert breakdown["supporting_count"] >= 1
    assert breakdown["total_evidence"] >= 1
