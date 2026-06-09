from typing import Any
from src.agents.tools.base import ToolBase
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
    NewsArticleNode, SocialPostNode, MetricDataNode, ProductNode,
    FeatureNode, FeatureMatrixNode, SentimentNode,
    PricingModelNode, TechStackNode, MarketPositionNode,
    SWOTNode, ScoringNode, InsightNode,
    ReportSectionNode, CrossReviewFlagNode,
    GraphEdge, EdgeType,
)


NODE_TYPE_MAP: dict[str, type] = {
    "SourceInfo": SourceInfoNode, "WebPage": WebPageNode,
    "ReviewEntry": ReviewEntryNode, "PricingData": PricingDataNode,
    "NewsArticle": NewsArticleNode, "SocialPost": SocialPostNode,
    "MetricData": MetricDataNode, "Product": ProductNode,
    "FeatureNode": FeatureNode, "FeatureMatrix": FeatureMatrixNode,
    "SentimentNode": SentimentNode, "PricingModel": PricingModelNode,
    "TechStack": TechStackNode, "MarketPosition": MarketPositionNode,
    "SWOTNode": SWOTNode, "ScoringNode": ScoringNode,
    "InsightNode": InsightNode, "ReportSection": ReportSectionNode,
    "CrossReviewFlag": CrossReviewFlagNode,
}


class GraphQueryTool(ToolBase):
    name = "graph_query"
    description = "Query nodes from the knowledge graph by type, layer, or ID."
    cacheable = False
    param_schema = {
        "node_type": {"type": "string", "description": "Node type to filter by"},
        "layer": {"type": "integer", "description": "Layer to filter by (1=raw, 2=analysis, 3=synthesis)"},
        "node_id": {"type": "string", "description": "Specific node ID to retrieve"},
        "include_all": {"type": "boolean", "description": "Set true to bypass task_id filtering for debugging."},
    }

    def __init__(self, store: GraphStore):
        self.store = store

    async def execute(self, **kwargs) -> dict[str, Any]:
        task_id = kwargs.get("_task_id", "")
        include_all = bool(kwargs.get("include_all", False))
        node_id = kwargs.get("node_id")
        if node_id:
            node = self.store.get_node(node_id)
            if node and task_id and not include_all and not self._belongs_to_task(node, task_id):
                return {"nodes": []}
            return {"nodes": [node.model_dump(mode="json")] if node else []}

        node_type = kwargs.get("node_type")
        layer = kwargs.get("layer")
        nodes = self.store.query_nodes(node_type=node_type, layer=layer)
        if task_id and not include_all:
            nodes = [n for n in nodes if self._belongs_to_task(n, task_id)]
        return {"nodes": [n.model_dump(mode="json") for n in nodes], "count": len(nodes)}

    @staticmethod
    def _belongs_to_task(node, task_id: str) -> bool:
        """按任务隔离图谱查询，避免 Agent 读取历史任务残留。"""
        metadata = getattr(node, "metadata", {}) or {}
        if isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        return metadata.get("task_id") == task_id


class GraphWriteTool(ToolBase):
    name = "graph_write"
    description = "Create nodes and edges in the knowledge graph."
    cacheable = False
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

        # Normalize: LLM may append "Node" suffix (e.g. "PricingModelNode" vs "PricingModel")
        cls = NODE_TYPE_MAP.get(node_type)
        if cls is None and node_type.endswith("Node"):
            cls = NODE_TYPE_MAP.get(node_type[:-4])
        if cls is None:
            return {"error": f"Unknown node type: '{node_type}'. Valid types: {list(NODE_TYPE_MAP.keys())}"}

        # Defensive normalization: map 'content' to 'text' if the target model expects 'text'
        if "content" in data and "text" not in data and "text" in cls.model_fields:
            data["text"] = data.pop("content")

        agent_type = kwargs.get("_agent_type", "")
        if agent_type:
            data["created_by"] = agent_type

        # inject task_id into metadata for analytics/report queries
        task_id = kwargs.get("_task_id", "")
        if task_id:
            existing_meta = data.get("metadata", {})
            if isinstance(existing_meta, str):
                try:
                    import json
                    existing_meta = json.loads(existing_meta)
                except (json.JSONDecodeError, TypeError):
                    existing_meta = {}
            existing_meta["task_id"] = task_id
            data["metadata"] = existing_meta

        try:
            node = cls(**data)
        except Exception as e:
            # Show LLM exactly what fields are needed so it can correct
            import inspect
            sig = inspect.signature(cls)
            required = [n for n, p in sig.parameters.items()
                        if p.default is inspect.Parameter.empty and n != "self"]
            return {
                "error": f"Failed to create {node_type}: {e}",
                "required_fields": required,
                "hint": f"Provide all required fields: {required}. Common mistake: ReportSection needs 'section' not 'title'.",
            }
        self.store.create_node(node)

        source_id = kwargs.get("source_id")
        edge_type_str = kwargs.get("edge_type")
        if source_id and edge_type_str:
            try:
                edge_type = EdgeType(edge_type_str)
            except ValueError:
                valid = [e.value for e in EdgeType]
                return {"node_id": node.id, "error": f"Invalid edge_type '{edge_type_str}'. Valid: {valid}"}
            edge = GraphEdge(
                source_id=source_id,
                target_id=node.id,
                edge_type=edge_type,
            )
            self.store.create_edge(edge)
            return {"node_id": node.id, "edge_id": edge.id}

        return {"node_id": node.id}
