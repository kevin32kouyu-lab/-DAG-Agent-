import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    InsightNode, ReportSectionNode, WebPageNode, SourceInfoNode,
    GraphEdge, EdgeType,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

# Lazy imports — will fail with ImportError if files are missing
from src.agents.qa_fact_check import QAFactCheckAgent
from src.agents.qa_logic_check import QALogicCheckAgent


@pytest.fixture
def qa_store(temp_db_path):
    """Store with a report section that has a complete trace chain."""
    store = GraphStore(db_path=temp_db_path)
    source = store.create_node(SourceInfoNode(
        url="https://g2.com", domain="g2.com", credibility_score=0.85,
    ))
    page = store.create_node(WebPageNode(
        url="https://g2.com/r", title="Reviews",
    ))
    insight = store.create_node(InsightNode(
        insight="Linear pricing targets mid-market teams", confidence=0.82,
    ))
    report = store.create_node(ReportSectionNode(
        section="Pricing Analysis",
        content="Linear targets mid-market teams...",
        order=3,
    ))
    store.create_edge(GraphEdge(
        source_id=page.id, target_id=source.id,
        edge_type=EdgeType.DERIVED_FROM,
    ))
    store.create_edge(GraphEdge(
        source_id=insight.id, target_id=page.id,
        edge_type=EdgeType.DERIVED_FROM,
    ))
    store.create_edge(GraphEdge(
        source_id=report.id, target_id=insight.id,
        edge_type=EdgeType.CITES,
    ))
    return store, {"source": source, "page": page, "insight": insight, "report": report}


@pytest.fixture
def qa_tools(qa_store):
    store, _ = qa_store
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return tools


@pytest.mark.asyncio
async def test_qa_fact_check_passes_on_complete_trace(qa_store, qa_tools):
    store, nodes = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({
            "reasoning": "Checking trace chain for insight",
            "action": "graph_query",
            "params": {"node_id": nodes["insight"].id},
            "confidence": 0.9,
        }), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({
            "reasoning": "Trace chain is complete - all assertions have supporting evidence",
            "action": "finalize",
            "result": {
                "summary": "All claims verified",
                "nodes_created": [], "edges_created": [],
                "data": {"failed_nodes": [], "issues": []},
            },
            "confidence": 0.95,
        }), model="test", tokens_in=100, tokens_out=50, cost=0.002),
    ])
    agent = QAFactCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    task = {
        "task_id": "t1", "node_id": "qa1",
        "agent_type": "QA_FactCheck",
        "input_query": {},
        "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.data.get("issues", []) == []


@pytest.mark.asyncio
async def test_qa_fact_check_fails_on_missing_trace(qa_store, qa_tools):
    store, nodes = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({
            "reasoning": "Checking trace chain",
            "action": "graph_query",
            "params": {"node_id": nodes["insight"].id},
            "confidence": 0.9,
        }), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({
            "reasoning": "Found an unverifiable claim - missing pricing data source",
            "action": "finalize",
            "result": {
                "summary": "1 claim unverifiable",
                "nodes_created": [], "edges_created": [],
                "data": {
                    "failed_nodes": [nodes["insight"].id],
                    "issues": [{
                        "node_id": nodes["insight"].id,
                        "reason": "Missing pricing data source",
                        "severity": "high",
                    }],
                },
            },
            "confidence": 0.9,
        }), model="test", tokens_in=100, tokens_out=60, cost=0.002),
    ])
    agent = QAFactCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    task = {
        "task_id": "t1", "node_id": "qa1",
        "agent_type": "QA_FactCheck",
        "input_query": {},
        "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert len(output.data.get("failed_nodes", [])) > 0


@pytest.mark.asyncio
async def test_qa_logic_check_runs(qa_store, qa_tools):
    store, _ = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({
            "reasoning": "Checking logical consistency of report",
            "action": "graph_query",
            "params": {"layer": 3},
            "confidence": 0.85,
        }), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({
            "reasoning": "No logical contradictions found in report",
            "action": "finalize",
            "result": {
                "summary": "Report is logically consistent",
                "nodes_created": [], "edges_created": [],
                "data": {"contradictions": []},
            },
            "confidence": 0.95,
        }), model="test", tokens_in=100, tokens_out=40, cost=0.002),
    ])
    agent = QALogicCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    task = {
        "task_id": "t1", "node_id": "qa2",
        "agent_type": "QA_LogicCheck",
        "input_query": {},
        "context": {},
    }
    output, traces = await agent.execute(task)
    assert output.status == "completed"
