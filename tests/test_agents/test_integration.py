import pytest
from unittest.mock import AsyncMock, MagicMock
from src.knowledge_graph.store import GraphStore
from src.agents.base import BaseAgent
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
async def test_agent_max_steps_exceeded(setup_integration):
    """Agent degrades gracefully when max_steps exhausted (circuit breaker test)."""
    store, gateway, tools, agent = setup_integration
    agent.max_steps = 2

    # Always respond with non-finalize — forces step exhaustion
    gateway.chat = AsyncMock(return_value=LLMResponse(
        content='{"reasoning": "keep going", "action": "graph_query", "params": {"node_type": "SourceInfo"}, "confidence": 0.5}',
        model="test", tokens_in=50, tokens_out=30, cost=0.001,
    ))

    task = {
        "task_id": "task_1", "node_id": "n1",
        "agent_type": "SimpleCollector",
        "input_query": {}, "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "degraded"
    assert output.confidence == 0.05
    assert len(traces) == agent.max_steps
