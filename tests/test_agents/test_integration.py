import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode
from src.agents.base import BaseAgent
from src.agents.context import AgentContext
from src.agents.contracts import AgentOutput
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class SimpleCollectorAgent(BaseAgent):
    agent_type = "SimpleCollector"
    system_prompt = "You are a data collector. Query the graph, then write a summary."
    max_steps = 5
    output_contract = AgentOutput


@pytest.fixture
def setup_integration(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    agent = SimpleCollectorAgent(gateway=gateway, store=store, tool_registry=tools)
    return store, gateway, tools, agent


@pytest.mark.asyncio
async def test_agent_execute_cycle_with_mock_gateway(setup_integration):
    store, gateway, tools, agent = setup_integration

    # Seed graph with test data
    store.create_node(SourceInfoNode(url="https://test.com", domain="test.com"))

    # Mock LLM to decide read → write → finalize in 3 steps
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content='{"reasoning": "Query for existing source info", "action": "graph_query", "params": {"node_type": "SourceInfo"}, "confidence": 0.8}',
            model="test", tokens_in=100, tokens_out=50, cost=0.001,
        ),
        LLMResponse(
            content='{"reasoning": "Found sources, now write a summary node", "action": "graph_write", "params": {"node_type": "InsightNode", "data": {"insight": "Test insight", "confidence": 0.8}}, "confidence": 0.85}',
            model="test", tokens_in=200, tokens_out=60, cost=0.002,
        ),
        LLMResponse(
            content='{"reasoning": "Done", "action": "finalize", "result": {"summary": "Collected data", "nodes_created": ["insight_1"], "edges_created": []}, "confidence": 0.9}',
            model="test", tokens_in=300, tokens_out=70, cost=0.003,
        ),
    ])

    task = {
        "task_id": "task_integration_1",
        "node_id": "collector_1",
        "agent_type": "SimpleCollector",
        "input_query": {"node_type": "SourceInfo"},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert len(traces) == 3
    assert traces[0].action == "graph_query"
    assert traces[1].action == "graph_write"
    assert traces[2].action == "finalize"


@pytest.mark.asyncio
async def test_agent_max_steps_exceeded(setup_integration):
    store, gateway, tools, agent = setup_integration
    agent.max_steps = 2

    # Always respond with non-finalize
    gateway.chat = AsyncMock(return_value=LLMResponse(
        content='{"reasoning": "keep going", "action": "graph_query", "params": {"node_type": "SourceInfo"}, "confidence": 0.5}',
        model="test", tokens_in=50, tokens_out=30, cost=0.001,
    ))

    task = {
        "task_id": "task_1", "node_id": "n1",
        "agent_type": "SimpleCollector",
        "input_query": {}, "context": {},
    }

    with pytest.raises(RuntimeError, match="exceeded max steps"):
        await agent.execute(task)
