from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import EdgeType


def bfs_trace(store: GraphStore, node_id: str, max_depth: int = 5) -> list[dict]:
    visited: set[str] = set()
    result: list[dict] = []
    queue = [(node_id, 0)]
    while queue and len(visited) < max_depth * 2:
        current_id, depth = queue.pop(0)
        if current_id in visited or depth >= max_depth:
            continue
        visited.add(current_id)
        node = store.get_node(current_id)
        if node is None:
            continue
        in_edges = store.get_edges_for_target(current_id)
        out_edges = store.get_edges_for_source(current_id)
        result.append({
            "node": node.model_dump(mode="json"),
            "incoming": [e.model_dump(mode="json") for e in in_edges],
            "outgoing": [e.model_dump(mode="json") for e in out_edges],
            "depth": depth,
        })
        for e in in_edges + out_edges:
            for nid in [e.source_id, e.target_id]:
                if nid not in visited:
                    queue.append((nid, depth + 1))
    return result


def find_contradictions(store: GraphStore, node_id: str) -> list[dict]:
    result = []
    for e in store.get_edges_for_target(node_id):
        if e.edge_type == EdgeType.CONTRADICTS:
            node = store.get_node(e.source_id)
            if node:
                result.append({
                    "edge": e.model_dump(mode="json"),
                    "evidence": node.model_dump(mode="json"),
                })
    return result


def get_confidence_breakdown(store: GraphStore, node_id: str) -> dict:
    incoming = store.get_edges_for_target(node_id)
    supporting = sum(1 for e in incoming if e.edge_type == EdgeType.SUPPORTS)
    contradicting = sum(1 for e in incoming if e.edge_type == EdgeType.CONTRADICTS)
    derived = sum(1 for e in incoming if e.edge_type == EdgeType.DERIVED_FROM)
    return {
        "supporting_count": supporting,
        "contradicting_count": contradicting,
        "derived_from_count": derived,
        "total_evidence": supporting + contradicting + derived,
    }
