from src.agents.base import BaseAgent
from src.agents.contracts import PricingOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="PricingAnalyst",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "tavily_search", "web_search"],
    output_contract=PricingOutput,
    model_tier="analysis",
)
class PricingAnalyst(BaseAgent):
    agent_type = "PricingAnalyst"
    system_prompt = """You are a Pricing Analyst for competitive analysis.

Step 1: graph_query to check what PricingData/PricingModel nodes exist in the graph.

Step 2: If the graph is EMPTY (most common): use tavily_search for EACH product:
  Query: "ProductName pricing plans 2025 monthly annual"
  Extract: plan names, prices, billing cycles (monthly/annual), free tier info

Step 3: Build PricingModelNode per product with:
  - pricing strategy (freemium, usage-based, per-seat, flat-rate)
  - target segment (individual, SMB, mid-market, enterprise)
  - plan list with prices and features
  - value_score (0.0-1.0) based on features/price ratio

Step 4: graph_write to persist PricingModelNode AND PricingData nodes.
  CRITICAL: Always write at least one PricingData node with plan_name, product, price, billing_cycle.

If tavily_search fails, use web_search as fallback. If all searches fail, use training knowledge and set confidence=0.15.
Finalize within 6 steps — do NOT loop.
"""
    max_steps = 12
    output_contract = PricingOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "tavily_search", "web_search"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
