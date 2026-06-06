import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from src.dag.models import DAGNode, NodeState
from src.dag.executor import AgentExecutor
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def executor(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return AgentExecutor(gateway=gateway, store=store, tool_registry=tools)


def test_executor_resolves_agent_class():
    ex = AgentExecutor.__new__(AgentExecutor)
    ex._agent_cache = {}
    ex.gateway = MagicMock()
    ex.store = MagicMock()
    ex.tool_registry = MagicMock()
    ex.audit_logger = None

    mock_cls = MagicMock()
    mock_mod = MagicMock()
    mock_mod.OrchestratorAgent = mock_cls

    with patch("importlib.import_module", return_value=mock_mod):
        cls = ex._resolve_agent_class("Orchestrator")
    assert cls is mock_cls


def test_executor_unknown_agent_type_has_clear_error():
    """未知 Agent 类型应给出可读错误，方便排查 DAG 配置。"""
    ex = AgentExecutor.__new__(AgentExecutor)
    ex._agent_cache = {}

    with pytest.raises(RuntimeError, match="未知 Agent 类型"):
        ex._resolve_agent_class("NonExistentAgent")


def test_executor_agent_import_failure_has_clear_error():
    """Agent 模块导入失败时应给出可读错误。"""
    from src.dag import executor as executor_module

    ex = AgentExecutor.__new__(AgentExecutor)
    ex._agent_cache = {}

    with patch.dict(
        executor_module._AGENT_IMPORT_MAP,
        {"BrokenAgent": ("src.agents.missing_agent", "MissingAgent")},
    ):
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("missing")):
            with pytest.raises(RuntimeError, match="Agent 导入失败：BrokenAgent"):
                ex._resolve_agent_class("BrokenAgent")


def test_executor_missing_agent_class_has_clear_error():
    """Agent 类名缺失时应给出可读错误。"""
    from src.dag import executor as executor_module

    ex = AgentExecutor.__new__(AgentExecutor)
    ex._agent_cache = {}

    with patch.dict(
        executor_module._AGENT_IMPORT_MAP,
        {"BrokenAgent": ("src.agents.broken_agent", "MissingAgent")},
    ):
        with patch("importlib.import_module", return_value=SimpleNamespace()):
            with pytest.raises(RuntimeError, match="Agent 类未找到：BrokenAgent"):
                ex._resolve_agent_class("BrokenAgent")


def test_executor_builds_task_from_node():
    node = DAGNode(
        node_id="collector_1", agent_type="Collector",
        input_query={"url": "https://notion.so"}, depends_on=["source_disc"],
        context={"schema_override": {"depth": "standard"}},
    )
    task = AgentExecutor._build_task(node, task_id="task_1")
    assert task["task_id"] == "task_1"
    assert task["node_id"] == "collector_1"
    assert task["agent_type"] == "Collector"
    assert task["input_query"]["url"] == "https://notion.so"


@pytest.mark.asyncio
async def test_executor_runs_node_and_returns_traces(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value=(MagicMock(status="completed"), []))

    ex = AgentExecutor(gateway=gateway, store=store, tool_registry=ToolRegistry())
    ex._build_agent = MagicMock(return_value=mock_agent)

    node = DAGNode(node_id="c1", agent_type="Collector",
                   input_query={"url": "https://test.com"}, depends_on=[])
    await ex.execute(node)

    mock_agent.execute.assert_called_once()
    # Scheduler handles state transition — executor only runs the agent
