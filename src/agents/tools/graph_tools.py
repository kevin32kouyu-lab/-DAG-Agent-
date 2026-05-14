from typing import Any
from src.agents.tools.base import ToolBase
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
    NewsArticleNode, SocialPostNode, MetricDataNode,
    FeatureNode, SentimentNode, PricingModelNode,
    SWOTNode, ScoringNode, InsightNode,
    ReportSectionNode, CrossReviewFlagNode,
    GraphEdge, EdgeType,
)


NODE_TYPE_MAP: dict[str, type] = {
    "SourceInfo": SourceInfoNode, "WebPage": WebPageNode,
    "ReviewEntry": ReviewEntryNode, "PricingData": PricingDataNode,
    "NewsArticle": NewsArticleNode, "SocialPost": SocialPostNode,
    "MetricData": MetricDataNode,
    "FeatureNode": FeatureNode, "SentimentNode": SentimentNode,
    "PricingModel": PricingModelNode, "SWOTNode": SWOTNode,
    "ScoringNode": ScoringNode,
    "InsightNode": InsightNode, "ReportSection": ReportSectionNode,
    "CrossReviewFlag": CrossReviewFlagNode,
}


class GraphQueryTool(ToolBase):
    name = "graph_query"
    description = "Query nodes from the knowledge graph by type, layer, or ID."
    param_schema = {
        "node_type": {"type": "string", "description": "Node type to filter by"},
        "layer": {"type": "integer", "description": "Layer to filter by (1=raw, 2=analysis, 3=synthesis)"},
        "node_id": {"type": "string", "description": "Specific node ID to retrieve"},
    }

    def __init__(self, store: GraphStore):
        self.store = store

    async def execute(self, **kwargs) -> dict[str, Any]:
        node_id = kwargs.get("node_id")
        if node_id:
            node = self.store.get_node(node_id)
            return {"nodes": [node.model_dump(mode="json")] if node else []}

        node_type = kwargs.get("node_type")
        layer = kwargs.get("layer")
        nodes = self.store.query_nodes(node_type=node_type, layer=layer)
        return {"nodes": [n.model_dump(mode="json") for n in nodes], "count": len(nodes)}


class GraphWriteTool(ToolBase):
    name = "graph_write"
    description = "Create nodes and edges in the knowledge graph."
    param_schema = {
        "node_type": {"type": "string", "description": "Type of node to create"},
        "data": {"type": "object", "description": "Node data matching the node type schema"},
        "source_id": {"type": "string", "description": "Source node ID for edge creation"},
        "edge_type": {"type": "string", "description": "Edge type: derived_from, supports, contradicts, related_to"},
    }

    def __init__(self, store: GraphStore):
        self.store = store

    async def execute(self, **kwargs) -> dict[str, Any]:
        node_type = kwargs.get("node_type", "")
        data = kwargs.get("data", {})
        data["label"] = data.get("label", data.get("name", data.get("url", "")))

        cls = NODE_TYPE_MAP.get(node_type)
        if cls is None:
            return {"error": f"Unknown node type: {node_type}"}

        node = cls(**data)
        self.store.create_node(node)

        source_id = kwargs.get("source_id")
        edge_type_str = kwargs.get("edge_type")
        if source_id and edge_type_str:
            edge = GraphEdge(
                source_id=source_id,
                target_id=node.id,
                edge_type=EdgeType(edge_type_str),
            )
            self.store.create_edge(edge)
            return {"node_id": node.id, "edge_id": edge.id}

        return {"node_id": node.id}
