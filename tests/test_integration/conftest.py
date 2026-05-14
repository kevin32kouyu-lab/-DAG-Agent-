import os
import pytest
from pathlib import Path
from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env before any integration test runs."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    # Verify required keys exist
    required = ["OPENAI_API_KEY_DEEPSEEK_CHAT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        pytest.exit(f"Missing required env vars: {missing}. Integration tests need real API keys.")


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
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=real_store)
    tools.register(GraphWriteTool, store=real_store)
    tools.register(WebScrapeTool)
    tools.register(WebSearchTool)
    return tools
