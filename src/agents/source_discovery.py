from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SourceDiscovery",
    depends_on=[],
    tools=["graph_query", "graph_write", "web_search", "tavily_search", "app_store", "producthunt", "google_trends", "social_media"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class SourceDiscoveryAgent(BaseAgent):
    agent_type = "SourceDiscovery"
    system_prompt = """You are a Source Discovery agent for competitive analysis.

Your job: for each target product, discover information sources using multiple free tools. Always try the most reliable tool first.

Available search/discovery tools (in priority order):
1. tavily_search — AI-powered web search, most reliable. Use search_depth="advanced" for comprehensive results.
2. app_store — Check if the product has a mobile app. Use action="search" with the product name to find app ratings, review counts, and update frequency.
3. producthunt — Check if the product launched on ProductHunt for community validation metrics.
4. google_trends — Compare search interest across multiple competitor products.
5. social_media — Search Chinese social platforms (小红书/知乎/微博) for brand mentions in China market.
6. web_search — Fallback only. DuckDuckGo scraping, may return empty.

Workflow:
1. Call tavily_search with queries like "ProductName pricing features reviews competitors"
2. Call app_store action="search" with the product name
3. Call producthunt action="search" with the product name
4. If Chinese market: call social_media with platform="xiaohongshu" or "zhihu"
5. FINALIZE after 3-4 tool calls maximum

CRITICAL — Handling empty results:
- If 2 tools return empty, FINALIZE IMMEDIATELY — do NOT keep retrying
- Set confidence low (0.1-0.3) when few sources found
- In your summary, report which tools succeeded and which failed

IMPORTANT: Discover URLs and product metadata. You do NOT need to create graph nodes — just report what you found.
"""
    max_steps = 7
    token_budget = 120_000
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_search", "tavily_search", "app_store", "producthunt", "google_trends", "social_media"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
