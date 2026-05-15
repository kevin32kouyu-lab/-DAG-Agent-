import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    FeatureNode, SentimentNode, PricingModelNode,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

# Lazy imports — will fail with ImportError if files are missing
from src.agents.swot_synthesizer import SWOTAnalyzer
from src.agents.writer import WriterAgent


def make_finalize_response(agent_type: str) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "reasoning": "Analysis complete",
            "action": "finalize",
            "result": {
                "summary": f"{agent_type} output",
                "nodes_created": ["n1"], "edges_created": ["e1"],
            },
            "confidence": 0.9,
        }),
        model="test", tokens_in=100, tokens_out=50, cost=0.002,
    )


@pytest.fixture
def swot_store(temp_db_path):
    """Store with Layer 2 analysis data for SWOT synthesis."""
    store = GraphStore(db_path=temp_db_path)
    feat = FeatureNode(
        product="Notion", name="Documents", category="Core",
        maturity="ga", differentiation="unique",
    )
    store.create_node(feat)
    sent = SentimentNode(
        product="Notion", topic="Usability",
        sentiment_score=0.7, trend="improving",
    )
    store.create_node(sent)
    price = PricingModelNode(
        product="Notion", strategy="freemium",
        target_segment="SMB", value_score=0.8,
    )
    store.create_node(price)
    return store


@pytest.fixture
def synth_tools(swot_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=swot_store)
    tools.register(GraphWriteTool, store=swot_store)
    return tools


@pytest.mark.asyncio
async def test_swot_synthesizer(swot_store, synth_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({
                "reasoning": "Reading Layer 2 analysis nodes for SWOT synthesis",
                "action": "graph_query",
                "params": {"layer": 2},
                "confidence": 0.85,
            }),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        make_finalize_response("SWOTAnalyzer"),
    ])

    agent = SWOTAnalyzer(
        gateway=gateway, store=swot_store, tool_registry=synth_tools,
    )
    task = {
        "task_id": "t1", "node_id": "sw1",
        "agent_type": "SWOTAnalyzer",
        "input_query": {"products": ["Notion"]},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.agent_type == "SWOTAnalyzer"


@pytest.mark.asyncio
async def test_writer_generates_report(swot_store, synth_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({
                "reasoning": "Reading all layers for report synthesis",
                "action": "graph_query",
                "params": {"layer": 3},
                "confidence": 0.8,
            }),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        make_finalize_response("Writer"),
    ])

    agent = WriterAgent(
        gateway=gateway, store=swot_store, tool_registry=synth_tools,
    )
    task = {
        "task_id": "t1", "node_id": "w1",
        "agent_type": "ReportGenerator",
        "input_query": {},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.agent_type == WriterAgent.agent_type
