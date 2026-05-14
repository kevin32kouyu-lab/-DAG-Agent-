import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import FeatureNode, SentimentNode
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

# Lazy import — will fail with ImportError if file is missing
from src.agents.cross_review import CrossReviewAgent


@pytest.fixture
def cr_store(temp_db_path):
    """Store seeded with a contradiction: Feature says docs=weak, Sentiment says positive."""
    store = GraphStore(db_path=temp_db_path)
    feat = FeatureNode(
        product="Linear", name="Documents", category="Core",
        maturity="ga", differentiation="disadvantage",
    )
    store.create_node(feat)
    sent = SentimentNode(
        product="Linear", topic="Documentation",
        sentiment_score=0.8, trend="improving",
    )
    store.create_node(sent)
    return store


@pytest.fixture
def cr_tools(cr_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=cr_store)
    tools.register(GraphWriteTool, store=cr_store)
    return tools


@pytest.mark.asyncio
async def test_cross_review_detects_contradictions(cr_store, cr_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({
                "reasoning": "Checking for contradictions between Feature and Sentiment",
                "action": "graph_query",
                "params": {"layer": 2},
                "confidence": 0.85,
            }),
            model="test", tokens_in=100, tokens_out=40, cost=0.002,
        ),
        LLMResponse(
            content=json.dumps({
                "reasoning": "Found contradiction: FeatureAnalyzer says Linear docs=weak, SentimentAnalyzer says positive",
                "action": "finalize",
                "result": {
                    "summary": "Detected 1 contradiction, 0 omissions, 0 anomalies",
                    "nodes_created": ["crf1"], "edges_created": ["ce1"],
                    "data": {
                        "flags": [{
                            "flag_type": "conflict",
                            "severity": "high",
                            "involved_agents": ["FeatureAnalyzer", "SentimentAnalyzer"],
                            "description": "Documentation feature score contradicts user sentiment",
                        }],
                    },
                },
                "confidence": 0.9,
            }),
            model="test", tokens_in=200, tokens_out=100, cost=0.004,
        ),
    ])

    agent = CrossReviewAgent(
        gateway=gateway, store=cr_store, tool_registry=cr_tools,
    )
    task = {
        "task_id": "t1", "node_id": "cr1",
        "agent_type": "CrossReviewAgent",
        "input_query": {"products": ["Linear"]},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    flags = output.data.get("flags", [])
    assert len(flags) >= 1
    assert flags[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_cross_review_no_issues_when_consistent(cr_store, cr_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({
                "reasoning": "Checking Layer 2 analysis nodes",
                "action": "graph_query",
                "params": {"layer": 2},
                "confidence": 0.9,
            }),
            model="test", tokens_in=100, tokens_out=40, cost=0.002,
        ),
        LLMResponse(
            content=json.dumps({
                "reasoning": "All analysis nodes are consistent",
                "action": "finalize",
                "result": {
                    "summary": "No issues found",
                    "nodes_created": [], "edges_created": [],
                    "data": {"flags": []},
                },
                "confidence": 0.95,
            }),
            model="test", tokens_in=200, tokens_out=60, cost=0.002,
        ),
    ])

    agent = CrossReviewAgent(
        gateway=gateway, store=cr_store, tool_registry=cr_tools,
    )
    task = {
        "task_id": "t2", "node_id": "cr2",
        "agent_type": "CrossReviewAgent",
        "input_query": {"products": ["Linear"]},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"


def test_cross_review_system_prompt_includes_contradicts_edges():
    """CrossReview agent system prompt should instruct creating contradicts edges."""
    prompt = CrossReviewAgent.system_prompt
    assert "contradicts" in prompt.lower()
    assert "edge" in prompt.lower()
