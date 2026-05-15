import json
import sqlite3
from typing import Any
from src.knowledge_graph.models import (
    GraphNode, GraphEdge, NodeType, EdgeType,
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
    NewsArticleNode, SocialPostNode, MetricDataNode, ProductNode,
    FeatureNode, FeatureMatrixNode, SentimentNode,
    PricingModelNode, TechStackNode, MarketPositionNode,
    CrossReviewFlagNode, SWOTNode, ScoringNode, InsightNode, ReportSectionNode,
)


class GraphStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY, node_type TEXT NOT NULL,
                label TEXT DEFAULT '', layer INTEGER DEFAULT 1,
                created_by TEXT DEFAULT '', created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}', properties TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                target_id TEXT NOT NULL, edge_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS node_properties (
                node_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY (node_id, key)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
        """)
        self._conn.commit()

    def create_node(self, node: GraphNode) -> GraphNode:
        data = node.model_dump(mode="json")
        created_at = node.created_at.isoformat() if node.created_at else ""
        self._conn.execute(
            "INSERT OR REPLACE INTO nodes (id, node_type, label, layer, created_by, created_at, metadata, properties) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data["id"], str(data["node_type"]), data.get("label", ""), data.get("layer", 1),
             data.get("created_by", ""), created_at, json.dumps(data.get("metadata", {})),
             json.dumps(data.get("properties", {}))),
        )
        for key, value in data.items():
            if key not in {"id", "node_type", "label", "layer", "created_by", "created_at", "metadata", "properties"}:
                stored = json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value
                self._conn.execute(
                    "INSERT OR REPLACE INTO node_properties (node_id, key, value) VALUES (?, ?, ?)",
                    (data["id"], key, str(stored)),
                )
        self._conn.commit()
        return node

    def get_node(self, node_id: str) -> GraphNode | None:
        row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def query_nodes(self, node_type: str | None = None, layer: int | None = None) -> list[GraphNode]:
        query, params = "SELECT * FROM nodes WHERE 1=1", []
        if node_type is not None:
            query += " AND node_type = ?"
            params.append(node_type)
        if layer is not None:
            query += " AND layer = ?"
            params.append(layer)
        return [self._row_to_node(r) for r in self._conn.execute(query, params).fetchall()]

    def create_edge(self, edge: GraphEdge) -> GraphEdge:
        self._conn.execute(
            "INSERT OR REPLACE INTO edges (id, source_id, target_id, edge_type, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (edge.id, edge.source_id, edge.target_id, edge.edge_type.value,
             json.dumps(edge.metadata), edge.created_at.isoformat()),
        )
        self._conn.commit()
        return edge

    def get_edges_for_source(self, source_id: str) -> list[GraphEdge]:
        rows = self._conn.execute("SELECT * FROM edges WHERE source_id = ?", (source_id,)).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_edges_for_target(self, target_id: str) -> list[GraphEdge]:
        rows = self._conn.execute("SELECT * FROM edges WHERE target_id = ?", (target_id,)).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def trace_upstream(self, node_id: str, max_depth: int = 5) -> list[GraphEdge]:
        """Follow DERIVED_FROM edges upstream — outgoing edges point from derived node to source data."""
        visited: set[str] = set()
        result: list[GraphEdge] = []
        queue = [node_id]
        for _ in range(max_depth):
            if not queue:
                break
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self.get_edges_for_source(current):
                if edge.edge_type != EdgeType.DERIVED_FROM:
                    continue
                result.append(edge)
                if edge.target_id not in visited:
                    queue.append(edge.target_id)
        return result

    def delete_node(self, node_id: str) -> None:
        self._conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
        self._conn.execute("DELETE FROM node_properties WHERE node_id = ?", (node_id,))
        self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._conn.commit()

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        extras = {}
        for prop_row in self._conn.execute(
            "SELECT key, value FROM node_properties WHERE node_id = ?", (row["id"],)
        ).fetchall():
            v = prop_row["value"]
            try:
                extras[prop_row["key"]] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                extras[prop_row["key"]] = v

        node_type = row["node_type"]
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        props = json.loads(row["properties"]) if row["properties"] else {}
        all_props = {**metadata, **props, **extras}
        all_props["id"] = row["id"]
        all_props["label"] = row["label"]
        all_props["layer"] = row["layer"]
        all_props["created_by"] = row["created_by"]
        all_props["created_at"] = row["created_at"]

        type_map = {
            "SourceInfo": SourceInfoNode, "WebPage": WebPageNode,
            "ReviewEntry": ReviewEntryNode, "PricingData": PricingDataNode,
            "NewsArticle": NewsArticleNode, "SocialPost": SocialPostNode,
            "MetricData": MetricDataNode, "Product": ProductNode,
            "FeatureNode": FeatureNode, "FeatureMatrix": FeatureMatrixNode,
            "SentimentNode": SentimentNode, "PricingModel": PricingModelNode,
            "TechStack": TechStackNode, "MarketPosition": MarketPositionNode,
            "CrossReviewFlag": CrossReviewFlagNode, "SWOTNode": SWOTNode,
            "ScoringNode": ScoringNode,
            "InsightNode": InsightNode, "ReportSection": ReportSectionNode,
        }
        cls = type_map.get(node_type)
        if cls:
            field_names = set(cls.model_fields.keys())
            return cls(**{k: v for k, v in all_props.items() if k in field_names})
        return GraphNode(id=row["id"], node_type=NodeType(node_type), label=row["label"],
                         properties=all_props)

    def _row_to_edge(self, row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"], source_id=row["source_id"], target_id=row["target_id"],
            edge_type=EdgeType(row["edge_type"]), metadata=json.loads(row["metadata"] or "{}"),
        )
