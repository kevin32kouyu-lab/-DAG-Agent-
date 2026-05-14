from src.agents.base import BaseAgent
from src.agents.contracts import SWOTOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SWOTAnalyzer",
    depends_on=["CrossReviewAgent"],
    tools=["graph_query", "graph_write"],
    output_contract=SWOTOutput,
    model_tier="analysis",
)
class SWOTAnalyzer(BaseAgent):
    agent_type = "SWOTAnalyzer"
    system_prompt = """You are a SWOT Analyzer. Synthesize all Layer 2 analysis into a SWOT matrix per product.

For each product, identify:
- Strengths: What the product does best (from FeatureMatrix, Sentiment positive, PricingModel value)
- Weaknesses: Gaps and weaknesses (from FeatureMatrix gaps, negative Sentiment, PricingModel concerns)
- Opportunities: Market trends and gaps (from MarketPosition, NewsArticle)
- Threats: Competitive threats and market risks (from competitive comparisons, MarketPosition)

If CrossReviewFlag nodes exist, incorporate their findings and note analyst disagreements.
"""
    max_steps = 12
    output_contract = SWOTOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
