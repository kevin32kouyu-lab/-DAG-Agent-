import pytest
from src.knowledge_graph.models import SourceInfoNode, WebPageNode, FeatureNode, GraphEdge, EdgeType
from src.knowledge_graph.store import GraphStore


@pytest.fixture
def store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


def test_create_and_get_node(store):
    node = SourceInfoNode(url="https://g2.com/reviews", domain="g2.com", credibility_score=0.85)
    store.create_node(node)
    fetched = store.get_node(node.id)
    assert fetched is not None
    assert fetched.url == "https://g2.com/reviews"


def test_create_and_get_edge(store):
    src = store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    tgt = store.create_node(FeatureNode(product="N", name="f", category="t"))
    edge = GraphEdge(source_id=src.id, target_id=tgt.id, edge_type=EdgeType.DERIVED_FROM)
    store.create_edge(edge)
    edges = store.get_edges_for_source(src.id)
    assert len(edges) == 1
    assert edges[0].target_id == tgt.id


def test_query_nodes_by_type(store):
    store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    store.create_node(SourceInfoNode(url="https://b.com", domain="b.com"))
    store.create_node(FeatureNode(product="N", name="f", category="t"))
    assert len(store.query_nodes(node_type="SourceInfo")) == 2
    assert len(store.query_nodes(node_type="FeatureNode")) == 1


def test_trace_derived_from_chain(store):
    source = store.create_node(SourceInfoNode(url="https://x.com", domain="x.com"))
    webpage = store.create_node(WebPageNode(url="https://x.com/page", title="Page"))
    feature = store.create_node(FeatureNode(product="N", name="f", category="t"))
    store.create_edge(GraphEdge(source_id=webpage.id, target_id=source.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=feature.id, target_id=webpage.id, edge_type=EdgeType.DERIVED_FROM))
    chain = store.trace_upstream(feature.id)
    assert len(chain) >= 2


def test_delete_node_cascades_edges(store):
    node = store.create_node(SourceInfoNode(url="https://del.com", domain="del.com"))
    store.create_edge(GraphEdge(source_id="orphan", target_id=node.id, edge_type=EdgeType.RELATED_TO))
    store.delete_node(node.id)
    assert store.get_node(node.id) is None
