from src.agents.base import BaseAgent
from src.agents.contracts import PricingOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="PricingAnalyst",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write"],
    output_contract=PricingOutput,
    model_tier="analysis",
)
class PricingAnalyst(BaseAgent):
    agent_type = "PricingAnalyst"
    system_prompt = """You are a Pricing Analyst for competitive analysis.

Analyze pricing models from PricingData nodes:
1. Identify pricing strategy (freemium, usage-based, per-seat, enterprise)
2. Determine target segment (individual, SMB, mid-market, enterprise)
3. Calculate value score based on features/price ratio
4. Build competitive comparison: who offers more for less?

Output: PricingModelNode per product. Include comparisons in the comparison field.
"""
    max_steps = 10
    output_contract = PricingOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
