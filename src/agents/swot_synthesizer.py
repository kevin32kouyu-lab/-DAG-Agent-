from src.agents.base import BaseAgent
from src.agents.contracts import SWOTOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SWOTAnalyzer",
    depends_on=["CrossReviewAgent"],
    tools=["graph_query", "graph_write", "tavily_search", "web_search"],
    output_contract=SWOTOutput,
    model_tier="analysis",
)
class SWOTAnalyzer(BaseAgent):
    agent_type = "SWOTAnalyzer"
    system_prompt = """You are a SWOT Analyzer. Synthesize all Layer 2 analysis into a SWOT matrix per product.

Step 1: graph_query to read FeatureMatrix, SentimentNode, PricingModel, MarketPosition.

Step 2: If graph data is THIN (fewer than 3 nodes per product): use tavily_search to fill gaps:
  Query: "ProductName strengths weaknesses review 2025"
  Query: "ProductName vs competitors comparison"

Step 3: For each product, write a SWOTNode with:
  - strengths: list 3-5 (from FeatureMatrix positives, high sentiments)
  - weaknesses: list 3-5 (from FeatureMatrix gaps, negative sentiments)
  - opportunities: list 3-5 (from MarketPosition insights, search results)
  - threats: list 3-5 (from competitive comparisons, market trends)

Step 4: graph_write to persist one SWOTNode per product.

CRITICAL: Always write SWOTNode to the graph — do NOT skip even if data is sparse.
Use training knowledge + search results if graph is empty. Set confidence accordingly.
Finalize within 8 steps.
"""
    max_steps = 15
    output_contract = SWOTOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "tavily_search", "web_search"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
