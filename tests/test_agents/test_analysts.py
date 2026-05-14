import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

# Lazy imports — test will fail with ImportError if files are missing
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.techstack_analyzer import TechStackAnalyzer
from src.agents.market_position import MarketPositionAnalyzer


AGENT_CLASSES = [
    FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst,
    TechStackAnalyzer, MarketPositionAnalyzer,
]


@pytest.fixture
def seeded_store(temp_db_path):
    """Store with Layer 1 data for analysis agents to work with."""
    store = GraphStore(db_path=temp_db_path)
    for product in ["Notion", "Confluence", "Linear"]:
        wp = WebPageNode(
            url=f"https://{product.lower()}.com",
            title=f"{product} Official",
            text=f"{product} is a collaborative tool for teams.",
        )
        store.create_node(wp)
        src = SourceInfoNode(
            url=f"https://{product.lower()}.com",
            domain=f"{product.lower()}.com",
            credibility_score=0.9,
        )
        store.create_node(src)
        rev = ReviewEntryNode(
            source="G2", rating=4.0,
            text=f"Great {product} features for collaboration",
        )
        store.create_node(rev)
        price = PricingDataNode(
            product=product, plan_name="Standard",
            price=10.0, currency="USD", billing_cycle="monthly",
        )
        store.create_node(price)
    return store


@pytest.fixture
def analysis_tools(seeded_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=seeded_store)
    tools.register(GraphWriteTool, store=seeded_store)
    return tools


@pytest.mark.parametrize("agent_cls", AGENT_CLASSES)
@pytest.mark.asyncio
async def test_analysis_agent_completes(agent_cls, seeded_store, analysis_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({
                "reasoning": "Reading Layer 1 data",
                "action": "graph_query",
                "params": {"layer": 1},
                "confidence": 0.85,
            }),
            model="test", tokens_in=100, tokens_out=40, cost=0.002,
        ),
        LLMResponse(
            content=json.dumps({
                "reasoning": "Analysis complete",
                "action": "finalize",
                "result": {
                    "summary": f"{agent_cls.agent_type} completed analysis",
                    "nodes_created": ["n1", "n2"],
                    "edges_created": ["e1", "e2"],
                },
                "confidence": 0.9,
            }),
            model="test", tokens_in=200, tokens_out=60, cost=0.003,
        ),
    ])

    agent = agent_cls(
        gateway=gateway, store=seeded_store, tool_registry=analysis_tools,
    )
    task = {
        "task_id": "t1", "node_id": agent_cls.agent_type,
        "agent_type": agent_cls.agent_type,
        "input_query": {"products": ["Notion", "Confluence", "Linear"]},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.agent_type == agent_cls.agent_type
    assert len(traces) >= 1
