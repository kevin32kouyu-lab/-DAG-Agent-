from src.agents.base import BaseAgent
from src.agents.contracts import MarketPositionOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="MarketPositionAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "web_search", "tavily_search", "google_trends", "social_media"],
    output_contract=MarketPositionOutput,
    model_tier="analysis",
)
class MarketPositionAnalyzer(BaseAgent):
    agent_type = "MarketPositionAnalyzer"
    system_prompt = """You are a Market Position Analyzer for competitive analysis.

Determine each product's market position:
1. Positioning statement (who they claim to serve)
2. GTM strategy (PLG, sales-led, channel, community)
3. Target audience (developer, PM, designer, enterprise)

Output: MarketPositionNode per product with fields: product, positioning, gtm_strategy, target_audience.

CRITICAL: If the knowledge graph has no market data (upstream enricher may have failed),
infer position from general knowledge of the product and set confidence low (0.1-0.3).
Finalize within 5 steps — do NOT loop looking for data that doesn't exist.
"""
    max_steps = 10
    output_contract = MarketPositionOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "web_search", "tavily_search", "google_trends", "social_media"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
