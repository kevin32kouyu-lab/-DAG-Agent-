import os
import pytest
from pathlib import Path
from dotenv import load_dotenv


def pytest_addoption(parser):
    parser.addoption("--record-fixtures", action="store_true", default=False,
                     help="Record LLM responses to fixture files instead of replaying")


def pytest_configure(config):
    """Load .env before any integration test runs."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


@pytest.fixture(scope="session")
def real_gateway():
    """LLM Gateway wired to real DeepSeek API."""
    from src.llm_gateway.gateway import LLMGateway
    return LLMGateway(
        default_model="deepseek-chat",
        model_map={
            "reasoning": "deepseek-chat",
            "analysis": "deepseek-chat",
            "batch": "deepseek-chat",
        },
        provider_map={
            "deepseek-chat": "openai_compatible",
        },
    )


@pytest.fixture(scope="function")
def real_store(tmp_path):
    """Graph store backed by a temp SQLite database."""
    from src.knowledge_graph.store import GraphStore
    db = str(tmp_path / "test_kg.db")
    return GraphStore(db_path=db)


@pytest.fixture(scope="function")
def real_tools(real_store):
    """Tool registry with graph tools wired to real store."""
    from src.agents.tools.base import ToolRegistry
    from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
    from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool
    from src.agents.tools.company_scope import CompanyScopeTool
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=real_store)
    tools.register(GraphWriteTool, store=real_store)
    tools.register(WebScrapeTool)
    tools.register(WebSearchTool)
    tools.register(CompanyScopeTool)
    return tools


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pipeline_smoke.json"


@pytest.fixture(scope="function")
def replay_executor(real_gateway, real_store, real_tools):
    """ReplayAgentExecutor loaded from the recorded fixture."""
    from src.dag.replay import ReplayAgentExecutor

    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture not found: {FIXTURE_PATH}. Run record_fixture.py first.")

    return ReplayAgentExecutor(
        gateway=real_gateway,
        store=real_store,
        tool_registry=real_tools,
        fixture_path=str(FIXTURE_PATH),
    )


@pytest.fixture(scope="function")
def recorded_dag(replay_executor):
    """TaskDAG reconstructed from the recorded fixture."""
    dag = replay_executor.get_recorded_dag()
    if dag is None:
        pytest.skip("No DAG in fixture")
    return dag
