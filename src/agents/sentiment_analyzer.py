from src.agents.base import BaseAgent
from src.agents.contracts import SentimentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SentimentAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "tavily_search", "web_search", "reddit"],
    output_contract=SentimentOutput,
    model_tier="batch",
)
class SentimentAnalyzer(BaseAgent):
    agent_type = "SentimentAnalyzer"
    system_prompt = """You are a Sentiment Analyzer for competitive analysis.

Step 1: graph_query to check existing SentimentNode/ReviewEntry data.
Step 2: If graph is EMPTY or has < 2 reviews per topic, use external sources:
  - tavily_search: "ProductName user reviews complaints praise 2025"
  - reddit action="search": "ProductName experience review" (find real user discussions)
Step 3: For each product, group findings by topic:
  - pricing, usability, performance, support, features, onboarding
Step 4: Calculate sentiment_score (-1.0 to +1.0) per topic, identify trend (improving/stable/declining)
Step 5: graph_write to persist SentimentNode per topic per product with fields:
  product, topic, sentiment_score, trend, source_count

CRITICAL: Always graph_write at least 2 SentimentNode per product. Use search results if graph is empty. Set confidence accordingly. Finalize within 8 steps.
"""
    max_steps = 12
    output_contract = SentimentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "tavily_search", "web_search", "reddit"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
