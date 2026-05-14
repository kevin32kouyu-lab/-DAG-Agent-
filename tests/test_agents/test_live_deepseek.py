"""
Integration tests using real DeepSeek LLM to verify P1-P3 functionality.
Run with: python -m pytest tests/test_agents/test_live_deepseek.py -v -s
Requires: .env with DEEPSEEK_API_KEY set
"""
import json
import pytest
from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.source_discovery import SourceDiscoveryAgent
from src.agents.collector import CollectorAgent
from src.agents.data_enricher import DataEnricherAgent


@pytest.fixture
def live_gateway():
    return LLMGateway(
        default_model="deepseek-chat",
        model_map={
            "reasoning": "deepseek-chat",
            "analysis": "deepseek-chat",
            "batch": "deepseek-chat",
        },
        provider_map={"deepseek-chat": "openai_compatible"},
    )


@pytest.fixture
def live_store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


@pytest.fixture
def live_tools(live_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=live_store)
    tools.register(GraphWriteTool, store=live_store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)
    return tools


# ── P1: Single agent ReAct loop ──


@pytest.mark.asyncio
async def test_p1_agent_react_loop_with_live_llm(live_gateway, live_store, live_tools):
    """P1: Agent executes ReAct loop with real LLM, writes to graph."""
    agent = SourceDiscoveryAgent(
        gateway=live_gateway, store=live_store, tool_registry=live_tools,
    )
    task = {
        "task_id": "live_p1", "node_id": "sd1", "agent_type": "SourceDiscovery",
        "input_query": {"targets": ["Notion"]}, "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed", f"Agent failed: {output}"
    assert len(traces) >= 1
    assert output.summary, "Expected non-empty summary"
    print(f"\nP1 PASS: {len(traces)} steps, summary={output.summary[:120]}")


# ── P3: SourceDiscovery ──


@pytest.mark.asyncio
async def test_p3_source_discovery_with_live_llm(live_gateway, live_store, live_tools):
    """P3: SourceDiscovery searches for real product info."""
    agent = SourceDiscoveryAgent(
        gateway=live_gateway, store=live_store, tool_registry=live_tools,
    )
    task = {
        "task_id": "live_p3_sd", "node_id": "sd1", "agent_type": "SourceDiscovery",
        "input_query": {"targets": ["Linear"]}, "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert len(traces) >= 1
    print(f"\nP3-SD PASS: {len(traces)} steps, nodes_created={output.nodes_created}")


# ── P3: Collector with web_search (avoids httpx cleanup issues on Windows) ──


@pytest.mark.asyncio
async def test_p3_collector_with_live_llm(live_gateway, live_store, live_tools):
    """P3: Collector uses web_search to find info about a product."""
    agent = CollectorAgent(
        gateway=live_gateway, store=live_store, tool_registry=live_tools,
    )
    task = {
        "task_id": "live_p3_col", "node_id": "c1", "agent_type": "Collector",
        "input_query": {"urls": [], "product": "Linear"},
        "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.summary, "Expected non-empty summary"
    print(f"\nP3-Collector PASS: {len(traces)} steps, summary={output.summary[:120]}")


# ── P3: Full collection chain (SD → Collector → Enricher) ──


@pytest.mark.asyncio
async def test_p3_full_collection_chain(live_gateway, live_store, live_tools):
    """P3 end-to-end: SourceDiscovery → Collector → DataEnricher with real LLM."""
    results = []

    for agent_cls, name, task_data in [
        (SourceDiscoveryAgent, "SourceDiscovery", {"targets": ["Notion"]}),
        (CollectorAgent, "Collector", {"urls": [], "product": "Notion"}),
        (DataEnricherAgent, "DataEnricher", {"products": ["Notion"]}),
    ]:
        agent = agent_cls(gateway=live_gateway, store=live_store, tool_registry=live_tools)
        task = {
            "task_id": "live_p3_full", "node_id": name.lower()[:3],
            "agent_type": name, "input_query": task_data, "context": {},
        }
        output, traces = await agent.execute(task)
        assert output.status == "completed", f"{name} failed: {output}"
        results.append((name, len(traces), output.summary[:120]))
        print(f"  {name}: {len(traces)} steps, summary={output.summary[:120]}")

    print(f"\nP3-FULL PASS: {len(results)} agents completed successfully")
