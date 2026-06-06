import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.base import BaseAgent, StepTrace
from src.agents.context import AgentContext
from src.agents.contracts import AgentOutput
from src.agents.tools.base import ToolRegistry
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class DummyAgent(BaseAgent):
    agent_type = "DummyAgent"
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
    return DummyAgent(
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
    assert agent.agent_type == "DummyAgent"
    assert agent.max_steps == 3


def test_agent_output_contract_validation():
    output = AgentOutput(
        agent_type="DummyAgent", node_id="node_1",
        summary="Completed analysis", confidence=0.9,
        nodes_created=["n1", "n2"], edges_created=["e1"],
    )
    valid = AgentOutput.model_validate(output.model_dump())
    assert valid.confidence == 0.9


def test_persist_trace_logs_audit_failure(agent, caplog):
    audit_logger = MagicMock()
    audit_logger.log_step_trace.side_effect = RuntimeError("audit unavailable")
    agent.audit_logger = audit_logger
    trace = StepTrace(task_id="task_1", node_id="node_1", agent_type="DummyAgent", step_number=0)

    caplog.set_level("WARNING", logger="src.agents.base")

    agent._persist_trace(trace)

    assert "步骤轨迹写入失败" in caplog.text
    assert "audit unavailable" in caplog.text


@pytest.mark.asyncio
async def test_observe_does_not_load_entire_graph_without_query(agent):
    """未指定节点范围时，不应把整个知识图谱塞进 LLM 观察内容。"""
    agent.store.query_nodes = MagicMock(return_value=[MagicMock(id="n1")])

    observation = await agent._observe({
        "task_id": "task_1",
        "node_id": "node_1",
        "agent_type": "DummyAgent",
        "input_query": {},
        "context": {},
    })

    agent.store.query_nodes.assert_not_called()
    assert observation["nodes"] == []
    assert observation["nodes_read"] == []
    assert observation["graph_query_required"] is True


@pytest.mark.asyncio
async def test_observe_hides_volatile_task_ids(agent):
    """发给 LLM 的观察内容不应包含每次都会变化的任务 ID。"""
    task_a = {
        "task_id": "task_a",
        "node_id": "node_a",
        "agent_type": "DummyAgent",
        "input_query": {"targets": ["Notion"]},
        "context": {"task_id": "task_a"},
    }
    task_b = {
        "task_id": "task_b",
        "node_id": "node_b",
        "agent_type": "DummyAgent",
        "input_query": {"targets": ["Notion"]},
        "context": {"task_id": "task_b"},
    }

    observation_a = await agent._observe(task_a)
    observation_b = await agent._observe(task_b)

    assert observation_a["task"] == observation_b["task"]
    assert "task_id" not in str(observation_a["task"])
    assert "node_id" not in str(observation_a["task"])
