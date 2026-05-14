import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    WebPageNode, SourceInfoNode, ReviewEntryNode, PricingDataNode,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.cross_review import CrossReviewAgent
from src.agents.swot_synthesizer import SWOTAnalyzer
from src.agents.writer import WriterAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse


def make_response(action="finalize", summary="done"):
    return LLMResponse(
        content=json.dumps({
            "reasoning": "Working through analysis",
            "action": action,
            "result" if action == "finalize" else "params": (
                {"summary": summary, "nodes_created": [], "edges_created": []}
                if action == "finalize" else {}
            ),
            "confidence": 0.8,
        }),
        model="test", tokens_in=50, tokens_out=30, cost=0.001,
    )


@pytest.mark.asyncio
async def test_full_analysis_pipeline(temp_db_path):
    """End-to-end analysis pipeline: analysis → cross-review → SWOT → writer."""
    store = GraphStore(db_path=temp_db_path)

    # Seed Layer 1 data
    for product in ["Notion", "Linear"]:
        store.create_node(WebPageNode(
            url=f"https://{product.lower()}.com",
            title=f"{product} Page",
        ))
        store.create_node(ReviewEntryNode(
            source="G2", rating=4.0, text=f"Good {product}",
        ))
        store.create_node(PricingDataNode(
            product=product, plan_name="Standard",
            price=10.0, currency="USD",
        ))

    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)

    agents = {
        "FeatureAnalyzer": FeatureAnalyzer(
            gateway=gateway, store=store, tool_registry=tools,
        ),
        "SentimentAnalyzer": SentimentAnalyzer(
            gateway=gateway, store=store, tool_registry=tools,
        ),
        "PricingAnalyst": PricingAnalyst(
            gateway=gateway, store=store, tool_registry=tools,
        ),
        "CrossReviewAgent": CrossReviewAgent(
            gateway=gateway, store=store, tool_registry=tools,
        ),
        "SWOTAnalyzer": SWOTAnalyzer(
            gateway=gateway, store=store, tool_registry=tools,
        ),
        "Writer": WriterAgent(
            gateway=gateway, store=store, tool_registry=tools,
        ),
    }

    # All agents finalize immediately for this integration smoke test
    gateway.chat = AsyncMock(side_effect=[
        make_response() for _ in range(20)
    ])

    # Phase 1: Run analysis agents (parallel in real system, sequential in test)
    for atype in ["FeatureAnalyzer", "SentimentAnalyzer", "PricingAnalyst"]:
        agent = agents[atype]
        task = {
            "task_id": "t1", "node_id": atype,
            "agent_type": atype,
            "input_query": {"products": ["Notion", "Linear"]},
            "context": {},
        }
        output, traces = await agent.execute(task)
        assert output.status == "completed", f"{atype} failed: {output.summary}"
        assert len(traces) >= 1, f"{atype} should have at least 1 trace"

    # Phase 2: Cross-Review
    cr_output, cr_traces = await agents["CrossReviewAgent"].execute({
        "task_id": "t1", "node_id": "cr1",
        "agent_type": "CrossReviewAgent",
        "input_query": {"products": ["Notion", "Linear"]},
        "context": {},
    })
    assert cr_output.status == "completed"

    # Phase 3: SWOT synthesis
    swot_output, swot_traces = await agents["SWOTAnalyzer"].execute({
        "task_id": "t1", "node_id": "sw1",
        "agent_type": "SWOTAnalyzer",
        "input_query": {"products": ["Notion", "Linear"]},
        "context": {},
    })
    assert swot_output.status == "completed"

    # Phase 4: Writer report
    writer_output, writer_traces = await agents["Writer"].execute({
        "task_id": "t1", "node_id": "w1",
        "agent_type": "Writer",
        "input_query": {},
        "context": {},
    })
    assert writer_output.status == "completed"

    # Verify all agents completed successfully
    assert cr_output.agent_type == "CrossReviewAgent"
    assert swot_output.agent_type == "SWOTAnalyzer"
    assert writer_output.agent_type == "Writer"
