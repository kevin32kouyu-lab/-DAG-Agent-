import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.data_enricher import DataEnricherAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def enricher_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return DataEnricherAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_enricher_adds_context(enricher_agent):
    enricher_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Querying collected data", "action": "graph_query", "params": {"layer": 1}, "confidence": 0.85}),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Enrichment complete", "action": "finalize", "result": {"summary": "Added industry context", "nodes_created": ["m1"], "edges_created": []}, "confidence": 0.8}),
            model="test", tokens_in=80, tokens_out=30, cost=0.002,
        ),
    ])

    task = {"task_id": "t1", "node_id": "e1", "agent_type": "DataEnricher",
            "input_query": {"products": ["Notion"]}, "context": {}}

    output, traces = await enricher_agent.execute(task)
    assert output.status == "completed"
