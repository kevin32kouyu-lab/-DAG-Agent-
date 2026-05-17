"""Quick script to record FeatureAnalyzer with empty graph."""
import asyncio, os, sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from tests.replay_gateway import record_agent_fixture, FIXTURE_DIR
from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.feature_analyzer import FeatureAnalyzer


async def main():
    gateway = LLMGateway(
        default_model="deepseek-chat",
        model_map={"reasoning": "deepseek-chat", "analysis": "deepseek-chat", "batch": "deepseek-chat"},
        provider_map={"deepseek-chat": "openai_compatible"},
    )
    store = GraphStore(db_path=":memory:")  # EMPTY — no seed data
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)

    task = {
        "task_id": "rec_empty", "node_id": "feat_empty",
        "agent_type": "FeatureAnalyzer",
        "input_query": {"products": ["Notion"]},
        "context": {},
    }

    path = FIXTURE_DIR / "feature_analyzer_empty.json"
    await record_agent_fixture(FeatureAnalyzer, "feature_analyzer_empty",
                               gateway, store, tools, task, path)
    print(f"Recorded → {path}")

asyncio.run(main())
