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


def test_graph_query_tool_filters_by_current_task_by_default(store):
    store.create_node(SourceInfoNode(
        url="https://current.com", domain="current.com",
        metadata={"task_id": "task_current"},
    ))
    store.create_node(SourceInfoNode(
        url="https://old.com", domain="old.com",
        metadata={"task_id": "task_old"},
    ))

    tool = GraphQueryTool(store=store)
    result = asyncio.run(tool.execute(node_type="SourceInfo", _task_id="task_current"))

    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["url"] == "https://current.com"


def test_graph_query_tool_include_all_bypasses_task_filter(store):
    store.create_node(SourceInfoNode(
        url="https://current.com", domain="current.com",
        metadata={"task_id": "task_current"},
    ))
    store.create_node(SourceInfoNode(
        url="https://old.com", domain="old.com",
        metadata={"task_id": "task_old"},
    ))

    tool = GraphQueryTool(store=store)
    result = asyncio.run(tool.execute(
        node_type="SourceInfo",
        _task_id="task_current",
        include_all=True,
    ))

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


def test_batch_web_scrape_tool_basic():
    from src.agents.tools.web_tools import BatchWebScrapeTool
    tool = BatchWebScrapeTool()
    # Empty execution validation
    res = asyncio.run(tool.execute())
    assert "error" in res

    # Parameter fallback processing validation (comma-separated string to list)
    res2 = asyncio.run(tool.execute(urls="https://example.org, https://example.net"))
    assert res2["total_requested"] == 2
    assert "urls" in res2
    assert len(res2["results"]) == 2


def test_third_party_api_tool_marks_mock_data():
    """第三方付费 API 未接入时，返回值必须明确标记为演示降级数据。"""
    from src.agents.tools.api_tools import ThirdPartyAPITool

    tool = ThirdPartyAPITool()
    result = asyncio.run(tool.execute(source="similarweb", query="example.com"))

    assert result["source"] == "similarweb"
    assert result["query"] == "example.com"
    assert result["is_mock"] is True
    assert result["data_source"] == "mock"
    assert result["confidence"] == "low"
    assert "MOCK" in result["data"]["note"]
