import pytest
import asyncio
from src.agents.tools.base import ToolBase, ToolRegistry, tool_registry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode


@pytest.fixture
def store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


def test_tool_base_interface():
    class TestTool(ToolBase):
        name = "test_tool"
        description = "A test tool"

        async def execute(self, **kwargs):
            return {"result": kwargs.get("input", "default")}

    tool = TestTool()
    assert tool.name == "test_tool"
    assert tool.param_schema == {}


def test_tool_registry_register_and_describe():
    registry = ToolRegistry()
    registry.register(GraphQueryTool)
    registry.register(GraphWriteTool)
    names = registry.list_tools()
    assert "graph_query" in names
    assert "graph_write" in names
    desc = registry.describe_tools()
    assert len(desc) == 2
    assert desc[0]["name"] == "graph_query"


def test_graph_query_tool_filters_by_type(store):
    store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    store.create_node(SourceInfoNode(url="https://b.com", domain="b.com"))
    tool = GraphQueryTool(store=store)
    result = asyncio.run(tool.execute(node_type="SourceInfo"))
    assert len(result["nodes"]) == 2


def test_graph_write_tool_creates_node(store):
    tool = GraphWriteTool(store=store)
    result = asyncio.run(tool.execute(
        node_type="SourceInfo",
        data={"url": "https://new.com", "domain": "new.com", "credibility_score": 0.7},
    ))
    assert "node_id" in result
    assert store.get_node(result["node_id"]) is not None


def test_graph_write_created_by_populated(store):
    tool = GraphWriteTool(store=store)
    result = asyncio.run(tool.execute(
        node_type="InsightNode",
        data={"insight": "test", "confidence": 0.8},
        _agent_type="FeatureAnalyzer",
    ))
    node = store.get_node(result["node_id"])
    assert node.created_by == "FeatureAnalyzer"


def test_graph_write_all_layer2_types(store):
    """Verify all analysis-layer node types can be written."""
    tool = GraphWriteTool(store=store)
    test_cases = [
        ("FeatureMatrix", {"products": ["A"], "dimensions": ["d"]}),
        ("TechStack", {"product": "A", "languages": ["Python"]}),
        ("MarketPosition", {"product": "A", "positioning": "leader"}),
        ("Product", {"name": "Notion", "category": "SaaS"}),
    ]
    for node_type, data in test_cases:
        result = asyncio.run(tool.execute(node_type=node_type, data=data))
        assert "node_id" in result, f"Failed to create {node_type}"
        assert store.get_node(result["node_id"]) is not None
