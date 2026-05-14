import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.source_discovery import SourceDiscoveryAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.collector import CollectorAgent


@pytest.fixture
def sd_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    return SourceDiscoveryAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_source_discovery_creates_source_info_nodes(sd_agent):
    sd_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Searching for Notion info", "action": "web_search", "params": {"query": "Notion SaaS review G2 ProductHunt"}, "confidence": 0.9}),
            model="test", tokens_in=50, tokens_out=40, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Found sources", "action": "finalize", "result": {
                "summary": "Discovered 3 sources",
                "nodes_created": ["s1", "s2", "s3"],
                "edges_created": ["e1"],
                "data": {
                    "sources": [
                        {"url": "https://g2.com/notion", "domain": "g2.com", "credibility_score": 0.85},
                        {"url": "https://producthunt.com/notion", "domain": "producthunt.com", "credibility_score": 0.7},
                        {"url": "https://notion.so", "domain": "notion.so", "credibility_score": 0.95},
                    ]
                }
            }, "confidence": 0.9}),
            model="test", tokens_in=100, tokens_out=80, cost=0.002,
        ),
    ])

    task = {"task_id": "t1", "node_id": "sd1", "agent_type": "SourceDiscovery",
            "input_query": {"targets": ["Notion"]}, "context": {}}

    output, traces = await sd_agent.execute(task)
    assert output.status == "completed"
    assert len(traces) >= 1


@pytest.fixture
def collector_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebScrapeTool)
    return CollectorAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_collector_scrapes_and_stores_webpage(collector_agent):
    collector_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Scraping Notion pricing", "action": "web_scrape", "params": {"url": "https://notion.so/pricing"}, "confidence": 0.9}),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Storing results", "action": "finalize", "result": {
                "summary": "Collected Notion pricing page",
                "nodes_created": ["wp1"], "edges_created": ["e1"],
                "data": {"page_title": "Notion Pricing"}
            }, "confidence": 0.95}),
            model="test", tokens_in=80, tokens_out=40, cost=0.002,
        ),
    ])

    mock_html = "<html><head><title>Notion Pricing</title></head><body><p>Free plan with essential features.</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = mock_html
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        task = {"task_id": "t1", "node_id": "c1", "agent_type": "Collector",
                "input_query": {"urls": ["https://notion.so/pricing"], "product": "Notion"},
                "context": {}}

        output, traces = await collector_agent.execute(task)
        assert output.status == "completed"
