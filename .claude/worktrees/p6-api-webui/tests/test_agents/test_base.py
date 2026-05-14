import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.base import BaseAgent, StepTrace
from src.agents.context import AgentContext
from src.agents.contracts import AgentOutput
from src.agents.tools.base import ToolRegistry
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class TestAgent(BaseAgent):
    agent_type = "TestAgent"
    system_prompt = "You are a test agent."
    max_steps = 3
    output_contract = AgentOutput


@pytest.fixture
def mock_gateway():
    gw = MagicMock(spec=LLMGateway)
    return gw


@pytest.fixture
def agent(mock_gateway, temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    tool_registry = ToolRegistry()
    return TestAgent(
        gateway=mock_gateway,
        store=store,
        tool_registry=tool_registry,
    )


def test_step_trace_creation():
    trace = StepTrace(
        task_id="task_1", node_id="node_1", agent_type="Test",
        step_number=0, reasoning="test", confidence=0.8,
        action="graph_query", action_params={"node_type": "SourceInfo"},
        nodes_read=["n1", "n2"], llm_tokens=100, llm_cost=0.001,
    )
    assert trace.agent_type == "Test"
    assert trace.confidence == 0.8


def test_agent_execute_requires_implemented_methods(agent):
    assert agent.agent_type == "TestAgent"
    assert agent.max_steps == 3


def test_agent_output_contract_validation():
    output = AgentOutput(
        agent_type="TestAgent", node_id="node_1",
        summary="Completed analysis", confidence=0.9,
        nodes_created=["n1", "n2"], edges_created=["e1"],
    )
    valid = AgentOutput.model_validate(output.model_dump())
    assert valid.confidence == 0.9
