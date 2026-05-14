from src.agents.base import BaseAgent
from src.agents.contracts import SentimentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SentimentAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write"],
    output_contract=SentimentOutput,
    model_tier="batch",
)
class SentimentAnalyzer(BaseAgent):
    agent_type = "SentimentAnalyzer"
    system_prompt = """You are a Sentiment Analyzer for competitive analysis.

Analyze user reviews and social mentions from the knowledge graph:
1. Group reviews by topic (pricing, usability, performance, support, features)
2. Calculate sentiment scores (-1.0 to +1.0) per topic per product
3. Identify trends: improving, stable, declining
4. Extract key verbatim quotes

Output: SentimentNode per topic per product. derived_from links to ReviewEntry nodes.
"""
    max_steps = 10
    output_contract = SentimentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
